// Command eagle is a command line interface to the local SteelEagle daemon
// (eagled), which it calls on the daemon's control socket.
//
//	eagle [-socket path] [-timeout duration] <command> [args]
//
// The commands are:
//
//	configure <config.toml>         replace the daemon's config, restarting it
//	restart                         restart the daemon and all of its services
//	list-services                   print the daemon's services
//	install-package [-tag tag] <url> install a package of plugins
//	remove-package <url>            remove an installed package
//	list-packages                   print the installed packages
//
// Package installs and removals take effect when the daemon next restarts.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"maps"
	"os"
	"os/signal"
	"slices"
	"strings"
	"text/tabwriter"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

const usage = `usage: eagle [flags] <command> [args]

Commands:
  configure <config.toml>          replace the daemon's config, restarting it
  restart                          restart the daemon and all of its services
  list-services                    print the daemon's services
  install-package [-tag tag] <url> install a package of plugins
  remove-package <url>             remove an installed package
  list-packages                    print the installed packages

Package installs and removals take effect when the daemon next restarts.

Flags:
`

// command is a subcommand, which parses its arguments args into fs and calls
// the daemon with client, printing to out.
type command struct {
	args string // positional arguments, for its usage
	run  func(ctx context.Context, client daemonpb.DaemonServiceClient, fs *flag.FlagSet, args []string, out io.Writer) error
}

var commands = map[string]command{
	"configure":       {"<config.toml>", configure},
	"restart":         {"", restart},
	"list-services":   {"", listServices},
	"install-package": {"[-tag tag] <url>", installPackage},
	"remove-package":  {"<url>", removePackage},
	"list-packages":   {"", listPackages},
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

// run runs eagle with the command line arguments args, returning the exit
// code.
func run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("eagle", flag.ContinueOnError)
	fs.SetOutput(stderr)
	fs.Usage = func() {
		fmt.Fprint(stderr, usage)
		fs.PrintDefaults()
	}
	socket := fs.String("socket", util.GetDaemonSocketPath(), "daemon control socket")
	timeout := fs.Duration("timeout", 5*time.Minute, "how long to wait for the daemon to answer")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if fs.NArg() == 0 {
		fs.Usage()
		return 2
	}
	name := fs.Arg(0)
	cmd, ok := commands[name]
	if !ok {
		fmt.Fprintf(stderr, "eagle: unknown command %q\n\n", name)
		fs.Usage()
		return 2
	}
	cmdFs := flag.NewFlagSet(name, flag.ContinueOnError)
	cmdFs.SetOutput(stderr)
	cmdFs.Usage = func() {
		fmt.Fprintf(stderr, "usage: eagle %s %s\n", name, cmd.args)
		cmdFs.PrintDefaults()
	}

	conn, err := grpc.NewClient("unix://"+*socket, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		fmt.Fprintf(stderr, "eagle: %v\n", err)
		return 1
	}
	defer conn.Close()
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	ctx, cancelTimeout := context.WithTimeout(ctx, *timeout)
	defer cancelTimeout()

	err = cmd.run(ctx, daemonpb.NewDaemonServiceClient(conn), cmdFs, fs.Args()[1:], stdout)
	var usageErr usageError
	switch {
	case errors.As(err, &usageErr):
		if usageErr.msg != "" {
			fmt.Fprintf(stderr, "eagle %s: %s\n", name, usageErr.msg)
		}
		cmdFs.Usage()
		return 2
	case err != nil:
		fmt.Fprintf(stderr, "eagle %s: %s\n", name, describe(err, *socket))
		return 1
	}
	return 0
}

// usageError is a command line the command can't run, explained by msg.
type usageError struct{ msg string }

func (e usageError) Error() string { return e.msg }

// parseArgs parses args into fs, which must leave n positional arguments.
func parseArgs(fs *flag.FlagSet, args []string, n int) error {
	if err := fs.Parse(args); err != nil {
		return usageError{}
	}
	if fs.NArg() != n {
		return usageError{fmt.Sprintf("want %d argument(s), got %d", n, fs.NArg())}
	}
	return nil
}

// describe explains an error from the daemon.
func describe(err error, socket string) string {
	s, ok := status.FromError(err)
	if !ok {
		return err.Error()
	}
	switch s.Code() {
	case codes.Unavailable:
		return fmt.Sprintf("could not reach eagled at %s; is it running? (%s)", socket, s.Message())
	case codes.PermissionDenied:
		return fmt.Sprintf("not allowed: %s (is the daemon locked to an orchestrator?)", s.Message())
	case codes.DeadlineExceeded:
		return "timed out waiting for eagled"
	}
	return s.Message()
}

// configure replaces the daemon's config with a config.toml file.
func configure(ctx context.Context, client daemonpb.DaemonServiceClient, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	content, err := os.ReadFile(fs.Arg(0))
	if err != nil {
		return err
	}
	req := daemonpb.ConfigureRequest_builder{ConfigToml: string(content)}.Build()
	if _, err := client.Configure(ctx, req); err != nil {
		return err
	}
	fmt.Fprintln(out, "config replaced; eagled is restarting")
	return nil
}

// restart restarts the daemon.
func restart(ctx context.Context, client daemonpb.DaemonServiceClient, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	if _, err := client.Restart(ctx, &daemonpb.RestartRequest{}); err != nil {
		return err
	}
	fmt.Fprintln(out, "eagled is restarting")
	return nil
}

// categoryNames are the names services are printed with, by category.
var categoryNames = map[daemonpb.ServiceCategory]string{
	daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:   "vehicle",
	daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:    "engine",
	daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR:   "monitor",
	daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR: "simulator",
	daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA:     "extra",
}

// listServices prints the daemon's services as a table.
func listServices(ctx context.Context, client daemonpb.DaemonServiceClient, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	resp, err := client.ListServices(ctx, &daemonpb.ListServicesRequest{})
	if err != nil {
		return err
	}
	if len(resp.GetServices()) == 0 {
		fmt.Fprintln(out, "no services")
	} else {
		w := tabwriter.NewWriter(out, 0, 0, 2, ' ', 0)
		fmt.Fprintln(w, "CATEGORY\tNAME\tPLUGIN\tSTATUS\tUPTIME\tPACKAGE\tERROR")
		for _, s := range resp.GetServices() {
			category, ok := categoryNames[s.GetSrv().GetCategory()]
			if !ok {
				category = s.GetSrv().GetCategory().String()
			}
			state, uptime := "stopped", "-"
			if s.GetRunning() {
				state, uptime = "running", s.GetUptime().AsDuration().Truncate(time.Second).String()
			}
			fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\t%s\t%s\n", category, s.GetSrv().GetName(), orDash(s.GetPlugin()),
				state, uptime, orDash(s.GetUrl()), orDash(s.GetError()))
		}
		if err := w.Flush(); err != nil {
			return err
		}
	}
	if unavailable := resp.GetUnavailable(); len(unavailable) > 0 {
		fmt.Fprintf(out, "\ncould not reach remote daemons: %s\n", strings.Join(unavailable, ", "))
	}
	return nil
}

// installPackage installs a package of plugins.
func installPackage(ctx context.Context, client daemonpb.DaemonServiceClient, fs *flag.FlagSet, args []string, out io.Writer) error {
	tag := fs.String("tag", "", "branch or commit to install (default: the default branch)")
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	req := daemonpb.InstallPackageRequest_builder{Url: fs.Arg(0)}.Build()
	if *tag != "" {
		req.SetTag(*tag)
	}
	if _, err := client.InstallPackage(ctx, req); err != nil {
		return err
	}
	fmt.Fprintf(out, "installed %s; run `eagle restart` to use it\n", fs.Arg(0))
	return nil
}

// removePackage removes an installed package.
func removePackage(ctx context.Context, client daemonpb.DaemonServiceClient, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	req := daemonpb.RemovePackageRequest_builder{Url: fs.Arg(0)}.Build()
	if _, err := client.RemovePackage(ctx, req); err != nil {
		return err
	}
	fmt.Fprintf(out, "removed %s; run `eagle restart` to stop using it\n", fs.Arg(0))
	return nil
}

// listPackages prints the installed packages as a table.
func listPackages(ctx context.Context, client daemonpb.DaemonServiceClient, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	resp, err := client.ListPackages(ctx, &daemonpb.ListPackagesRequest{})
	if err != nil {
		return err
	}
	if len(resp.GetPackages()) == 0 {
		fmt.Fprintln(out, "no packages")
		return nil
	}
	w := tabwriter.NewWriter(out, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "URL\tTAG\tMODIFIED\tPLUGINS")
	for _, p := range resp.GetPackages() {
		modified := "-"
		if p.HasModified() {
			modified = p.GetModified().AsTime().Local().Format(time.DateTime)
		}
		plugins := strings.Join(slices.Sorted(maps.Keys(p.GetPlugins())), ", ")
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n", p.GetUrl(), orDash(p.GetTag()), modified, orDash(plugins))
	}
	return w.Flush()
}

// orDash returns s, or "-" if it is empty, so table cells are never blank.
func orDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}
