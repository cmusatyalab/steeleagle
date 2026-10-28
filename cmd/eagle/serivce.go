package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"maps"
	"net"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"text/tabwriter"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

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
func configure(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	content, err := os.ReadFile(fs.Arg(0))
	if err != nil {
		return err
	}
	req := daemonpb.ConfigureRequest_builder{ConfigToml: string(content)}.Build()
	if _, err := daemonpb.NewDaemonServiceClient(conn).Configure(ctx, req); err != nil {
		return err
	}
	fmt.Fprintln(out, "config replaced; eagled is restarting")
	return nil
}

// getConfig prints the daemon's config.toml.
func getConfig(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	resp, err := daemonpb.NewDaemonServiceClient(conn).GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
	if err != nil {
		return err
	}
	_, err = out.Write(resp.GetConfigToml())
	return err
}

// setOrchestrator replaces the daemon's config with the same config, but
// with its orchestrator set to host and port.
func setOrchestrator(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 2); err != nil {
		return err
	}
	host := fs.Arg(0)
	if host == "" {
		return usageError{"host must not be empty"}
	}
	port, err := strconv.Atoi(fs.Arg(1))
	if err != nil || port < 1 || port > 65535 {
		return usageError{fmt.Sprintf("invalid port %q", fs.Arg(1))}
	}
	client := daemonpb.NewDaemonServiceClient(conn)
	resp, err := client.GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
	if err != nil {
		return err
	}
	cfg, err := config.ParseDaemonConfigFromBytes(resp.GetConfigToml())
	if err != nil {
		return fmt.Errorf("daemon's config is invalid: %w", err)
	}
	cfg.Daemon.Orchestrator = net.JoinHostPort(host, strconv.Itoa(port))
	content, err := cfg.ToBytes()
	if err != nil {
		return err
	}
	req := daemonpb.ConfigureRequest_builder{ConfigToml: string(content)}.Build()
	if _, err := client.Configure(ctx, req); err != nil {
		return err
	}
	fmt.Fprintf(out, "orchestrator set to %s; eagled is restarting\n", cfg.Daemon.Orchestrator)
	return nil
}

// connectionStatus prints whether the daemon is connected to its
// orchestrator.
func connectionStatus(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	resp, err := daemonpb.NewDaemonServiceClient(conn).GetConnectionStatus(ctx, &daemonpb.GetConnectionStatusRequest{})
	if err != nil {
		return err
	}
	if resp.GetConnected() {
		fmt.Fprintln(out, "connected")
	} else {
		fmt.Fprintln(out, "not connected to orchestrator")
	}
	return nil
}

// restart restarts the daemon.
func restart(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	if _, err := daemonpb.NewDaemonServiceClient(conn).Restart(ctx, &daemonpb.RestartRequest{}); err != nil {
		return err
	}
	fmt.Fprintln(out, "eagled is restarting")
	return nil
}

// restartService restarts one of the daemon's services, by its name as
// list-services prints it.
func restartService(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	req := daemonpb.RestartServiceRequest_builder{ServiceNames: fs.Arg(0)}.Build()
	if _, err := daemonpb.NewDaemonServiceClient(conn).RestartService(ctx, req); err != nil {
		return err
	}
	fmt.Fprintf(out, "restarted %s\n", fs.Arg(0))
	return nil
}

// categoryNames are the names services are printed with, by category.
var categoryNames = map[daemonpb.ServiceCategory]string{
	daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:   "vehicle",
	daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:    "engine",
	daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR: "simulator",
	daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA:     "extra",
}

// isolationNames are the names isolations are printed with.
var isolationNames = map[daemonpb.Isolation]string{
	daemonpb.Isolation_ISOLATION_PROCESS:   "process",
	daemonpb.Isolation_ISOLATION_SANDBOX:   "sandbox",
	daemonpb.Isolation_ISOLATION_CONTAINER: "container",
}

// listServices prints the daemon's services as a table, followed by its
// remote daemons, if it has any.
func listServices(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	resp, err := daemonpb.NewDaemonServiceClient(conn).ListServices(ctx, &daemonpb.ListServicesRequest{})
	if err != nil {
		return err
	}
	if len(resp.GetServices()) == 0 {
		fmt.Fprintln(out, "no services")
	} else {
		w := tabwriter.NewWriter(out, 0, 0, 2, ' ', 0)
		fmt.Fprintln(w, "CATEGORY\tNAME\tPLUGIN\tSTATUS\tISOLATION\tAUTH\tPACKAGE")
		for _, s := range resp.GetServices() {
			category, ok := categoryNames[s.GetCategory()]
			if !ok {
				category = s.GetCategory().String()
			}
			isolation, ok := isolationNames[s.GetIsolation()]
			if !ok {
				isolation = "-"
			}
			state := "stopped"
			if s.GetRunning() {
				state = "running"
			}
			fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\t%s\t%s\n", category, s.GetName(), orDash(s.GetPlugin()),
				state, isolation, orDash(s.GetAuth()), orDash(s.GetUri()))
		}
		if err := w.Flush(); err != nil {
			return err
		}
	}
	if len(resp.GetRemotes()) == 0 {
		return nil
	}
	fmt.Fprintln(out)
	w := tabwriter.NewWriter(out, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "REMOTE\tHOSTNAME\tPLATFORM\tSTATUS")
	for _, d := range resp.GetRemotes() {
		platform := "-"
		if d.GetOs() != "" || d.GetArch() != "" {
			platform = d.GetOs() + "/" + d.GetArch()
		}
		state := "available"
		if d.GetError() != "" {
			state = "unavailable: " + d.GetError()
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n", d.GetIp(), orDash(d.GetHostname()), platform, state)
	}
	return w.Flush()
}

// installPackage installs a package of plugins.
func installPackage(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	req := daemonpb.InstallPackageRequest_builder{Uri: fs.Arg(0)}.Build()
	if _, err := daemonpb.NewDaemonServiceClient(conn).InstallPackage(ctx, req); err != nil {
		return err
	}
	fmt.Fprintf(out, "installed %s; run `eagle restart` to use it\n", fs.Arg(0))
	return nil
}

// removePackage removes an installed package.
func removePackage(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	req := daemonpb.RemovePackageRequest_builder{Uri: fs.Arg(0)}.Build()
	if _, err := daemonpb.NewDaemonServiceClient(conn).RemovePackage(ctx, req); err != nil {
		return err
	}
	fmt.Fprintf(out, "removed %s; run `eagle restart` to stop using it\n", fs.Arg(0))
	return nil
}

// listPackages prints the installed packages as a table.
func listPackages(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	resp, err := daemonpb.NewDaemonServiceClient(conn).ListPackages(ctx, &daemonpb.ListPackagesRequest{})
	if err != nil {
		return err
	}
	if len(resp.GetPackages()) == 0 {
		fmt.Fprintln(out, "no packages")
		return nil
	}
	w := tabwriter.NewWriter(out, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "URI\tMODIFIED\tPLUGINS")
	for _, p := range resp.GetPackages() {
		modified := "-"
		if p.HasModified() {
			modified = p.GetModified().AsTime().Local().Format(time.DateTime)
		}
		plugins := strings.Join(slices.Sorted(maps.Keys(p.GetPlugins())), ", ")
		fmt.Fprintf(w, "%s\t%s\t%s\n", p.GetUri(), modified, orDash(plugins))
	}
	return w.Flush()
}

// transferFile copies a file to the daemon's files directory.
func transferFile(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	name := fs.String("name", "", "name to save the file as (default: the file's base name)")
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	stream, err := daemonpb.NewTransferServiceClient(conn).TransferFile(ctx)
	if err != nil {
		return err
	}
	saved, err := sendChunks(fs.Arg(0), *name,
		func(chunk []byte, number, total int32, filename string) error {
			return stream.Send(daemonpb.TransferFileRequest_builder{
				Chunk: chunk, Number: number, Total: total, Filename: filename,
			}.Build())
		},
		func() (int32, error) {
			resp, err := stream.Recv()
			return resp.GetReceived(), err
		})
	if err != nil {
		return err
	}
	fmt.Fprintf(out, "transferred %s to the daemon's files\n", saved)
	return stream.CloseSend()
}

// transferModel copies a model to the daemon's models directory, which
// engines can read.
func transferModel(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	name := fs.String("name", "", "name to save the model as (default: the file's base name)")
	if err := parseArgs(fs, args, 1); err != nil {
		return err
	}
	stream, err := daemonpb.NewTransferServiceClient(conn).TransferModel(ctx)
	if err != nil {
		return err
	}
	saved, err := sendChunks(fs.Arg(0), *name,
		func(chunk []byte, number, total int32, filename string) error {
			return stream.Send(daemonpb.TransferModelRequest_builder{
				Chunk: chunk, Number: number, Total: total, Filename: filename,
			}.Build())
		},
		func() (int32, error) {
			resp, err := stream.Recv()
			return resp.GetReceived(), err
		})
	if err != nil {
		return err
	}
	fmt.Fprintf(out, "transferred %s to the daemon's models\n", saved)
	return stream.CloseSend()
}

// sendChunks sends the file at path in chunks numbered from 1, naming it name
// in the first chunk, or its base name if name is empty. Each chunk is sent
// once the one before it is acknowledged by recv, and the last is acknowledged
// once the daemon has saved the file. It returns the name the file was saved
// as.
func sendChunks(
	path, name string,
	send func(chunk []byte, number, total int32, filename string) error,
	recv func() (int32, error),
) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return "", err
	}
	if !info.Mode().IsRegular() {
		return "", fmt.Errorf("%s is not a regular file", path)
	}
	if name == "" {
		name = filepath.Base(path)
	}
	// An empty file is still sent as one empty chunk
	total := max(1, (info.Size()+chunkSize-1)/chunkSize)
	if total > 1<<31-1 {
		return "", fmt.Errorf("%s is too large to transfer", path)
	}
	buf := make([]byte, chunkSize)
	for number := int32(1); number <= int32(total); number++ {
		n, err := io.ReadFull(f, buf)
		// The last chunk may be short, or empty for an empty file
		if err != nil && !errors.Is(err, io.ErrUnexpectedEOF) && !errors.Is(err, io.EOF) {
			return "", err
		}
		filename := ""
		if number == 1 {
			filename = name
		}
		if err := send(buf[:n], number, int32(total), filename); err != nil {
			return "", recvErr(err, recv)
		}
		received, err := recv()
		if err != nil {
			return "", err
		}
		if received != number {
			return "", fmt.Errorf("daemon acknowledged chunk %d, want %d", received, number)
		}
	}
	return name, nil
}

// recvErr returns the status of a stream whose send failed with err, which
// gRPC only reports through recv.
func recvErr(err error, recv func() (int32, error)) error {
	if !errors.Is(err, io.EOF) {
		return err
	}
	if _, recvErr := recv(); recvErr != nil {
		return recvErr
	}
	return err
}

// orDash returns s, or "-" if it is empty, so table cells are never blank.
func orDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}
