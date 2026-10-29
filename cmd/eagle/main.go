// Command eagle is a command line interface to the local SteelEagle daemon
// (eagled), which it calls on the daemon's control socket.
//
//	eagle [-socket path] [-timeout duration] <command> [args]
//
// The commands are:
//
//	init                            install and start eagled as a service, and set it up
//	configure <config.toml>         replace the daemon's config, restarting it
//	get-config                      print the daemon's config
//	set-orchestrator <host> <port>  point the daemon at an orchestrator, restarting it
//	status                          print whether the daemon reaches its orchestrator
//	restart                         restart the daemon and all of its services
//	restart-service <name>          restart one service
//	list-services                   print the daemon's services and remote daemons
//	install-package <uri>           install a package of plugins
//	remove-package <uri>            remove an installed package
//	list-packages                   print the installed packages
//	transfer-file [-name name] <path>  copy a file to the daemon's files
//	transfer-model [-name name] <path> copy a model to the daemon's models
//
// A package uri has the form repo[//subdir][@version], and a package is
// removed by the uri it was installed with. Package installs and removals take
// effect when the daemon next restarts.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"time"

	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"google.golang.org/grpc"
	"google.golang.org/grpc/backoff"
	"google.golang.org/grpc/credentials/insecure"
)

const usage = `usage: eagle [flags] <command> [args]

Commands:
  init                               install and start eagled as a service, and set it up
  configure <config.toml>            replace the daemon's config, restarting it
  get-config                         print the daemon's config
  set-orchestrator <host> <port>     point the daemon at an orchestrator, restarting it
  status                             print whether the daemon reaches its orchestrator
  restart                            restart the daemon and all of its services
  restart-service <name>             restart one service
  list-services                      print the daemon's services and remote daemons
  install-package <uri>              install a package of plugins
  remove-package <uri>               remove an installed package
  list-packages                      print the installed packages
  transfer-file [-name name] <path>  copy a file to the daemon's files
  transfer-model [-name name] <path> copy a model to the daemon's models

A package uri has the form repo[//subdir][@version], and a package is removed
by the uri it was installed with. Package installs and removals take effect
when the daemon next restarts.

Flags:
`

// chunkSize is the size of the chunks files are transferred in, well under
// gRPC's default message size limit.
const chunkSize = 1 << 20

// command is a subcommand, which parses its arguments args into fs and calls
// the daemon over conn, printing to out.
type command struct {
	args string // positional arguments, for its usage
	run  func(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error
}

var commands = map[string]command{
	"init":             {"", initDaemon},
	"configure":        {"<config.toml>", configure},
	"get-config":       {"", getConfig},
	"set-orchestrator": {"<host> <port>", setOrchestrator},
	"status":           {"", connectionStatus},
	"restart":          {"", restart},
	"restart-service":  {"<name>", restartService},
	"list-services":    {"", listServices},
	"install-package":  {"<uri>", installPackage},
	"remove-package":   {"<uri>", removePackage},
	"list-packages":    {"", listPackages},
	"transfer-file":    {"[-name name] <path>", transferFile},
	"transfer-model":   {"[-name name] <path>", transferModel},
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

// run runs eagle with the command line arguments args, returning the exit
// code. Exits early if timeout is reached (except for init).
func run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("eagle", flag.ContinueOnError)
	fs.SetOutput(stderr)
	fs.Usage = func() {
		fmt.Fprint(stderr, usage)
		fs.PrintDefaults()
	}
	socket := fs.String("socket", util.GetDaemonSocketPath(), "daemon control socket")
	timeout := fs.Duration("timeout", 5*time.Minute, "how long to wait for the daemon to answer (not applied to init)")
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

	conn, err := grpc.NewClient("unix://"+*socket,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		// Reconnect quickly, so that init sees eagled as soon as it is up
		grpc.WithConnectParams(grpc.ConnectParams{
			Backoff:           backoff.Config{BaseDelay: 100 * time.Millisecond, Multiplier: 1.6, Jitter: 0.2, MaxDelay: time.Second},
			MinConnectTimeout: 5 * time.Second,
		}),
	)
	if err != nil {
		fmt.Fprintf(stderr, "eagle: %v\n", err)
		return 1
	}
	defer conn.Close()
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	// init waits on the user's answers to its prompts, which may take longer
	if name != "init" {
		var cancelTimeout context.CancelFunc
		ctx, cancelTimeout = context.WithTimeout(ctx, *timeout)
		defer cancelTimeout()
	}

	err = cmd.run(ctx, conn, cmdFs, fs.Args()[1:], stdout)
	var usageErr usageError
	switch {
	case errors.As(err, &usageErr):
		if usageErr.msg != "" {
			fmt.Fprintf(stderr, "eagle %s: %s\n", name, usageErr.msg)
		}
		cmdFs.Usage()
		return 2
	case err != nil:
		msg := fmt.Sprintf("eagle %s: %s", name, describe(err, *socket))
		if isTerminal(stderr) {
			msg = errorStyle.Render(msg)
		}
		fmt.Fprintln(stderr, msg)
		return 1
	}
	return 0
}
