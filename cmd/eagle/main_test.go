package main

import (
	"bytes"
	"context"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util/download"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// fakeDaemon records the calls eagle makes, answering with services,
// packages, its config and connection status, and failing every call with
// err. Transfers are saved to dir, as the daemon saves them.
type fakeDaemon struct {
	daemonpb.UnimplementedDaemonServiceServer
	daemonpb.UnimplementedTransferServiceServer
	err       error
	services  *daemonpb.ListServicesResponse
	packages  *daemonpb.ListPackagesResponse
	connected bool
	dir       string
	calls     []string
	config    string
	install   string
	remove    string
	restarted string
}

func (f *fakeDaemon) GetConfiguration(context.Context, *daemonpb.GetConfigurationRequest) (*daemonpb.GetConfigurationResponse, error) {
	f.calls = append(f.calls, "GetConfiguration")
	return daemonpb.GetConfigurationResponse_builder{ConfigToml: []byte(f.config)}.Build(), f.err
}

func (f *fakeDaemon) GetConnectionStatus(context.Context, *daemonpb.GetConnectionStatusRequest) (*daemonpb.GetConnectionStatusResponse, error) {
	f.calls = append(f.calls, "GetConnectionStatus")
	return daemonpb.GetConnectionStatusResponse_builder{Connected: f.connected}.Build(), f.err
}

func (f *fakeDaemon) RestartService(_ context.Context, req *daemonpb.RestartServiceRequest) (*daemonpb.RestartServiceResponse, error) {
	f.calls = append(f.calls, "RestartService")
	f.restarted = req.GetServiceNames()
	return &daemonpb.RestartServiceResponse{}, f.err
}

func (f *fakeDaemon) TransferFile(stream grpc.BidiStreamingServer[daemonpb.TransferFileRequest, daemonpb.TransferFileResponse]) error {
	f.calls = append(f.calls, "TransferFile")
	return download.DownloadFile(zerolog.Nop(), stream, f.dir, func(number int32) *daemonpb.TransferFileResponse {
		return daemonpb.TransferFileResponse_builder{Received: number}.Build()
	})
}

func (f *fakeDaemon) TransferModel(stream grpc.BidiStreamingServer[daemonpb.TransferModelRequest, daemonpb.TransferModelResponse]) error {
	f.calls = append(f.calls, "TransferModel")
	return download.DownloadFile(zerolog.Nop(), stream, f.dir, func(number int32) *daemonpb.TransferModelResponse {
		return daemonpb.TransferModelResponse_builder{Received: number}.Build()
	})
}

func (f *fakeDaemon) Configure(_ context.Context, req *daemonpb.ConfigureRequest) (*daemonpb.ConfigureResponse, error) {
	f.calls = append(f.calls, "Configure")
	f.config = req.GetConfigToml()
	return &daemonpb.ConfigureResponse{}, f.err
}

func (f *fakeDaemon) Restart(context.Context, *daemonpb.RestartRequest) (*daemonpb.RestartResponse, error) {
	f.calls = append(f.calls, "Restart")
	return &daemonpb.RestartResponse{}, f.err
}

func (f *fakeDaemon) ListServices(context.Context, *daemonpb.ListServicesRequest) (*daemonpb.ListServicesResponse, error) {
	f.calls = append(f.calls, "ListServices")
	return f.services, f.err
}

func (f *fakeDaemon) InstallPackage(_ context.Context, req *daemonpb.InstallPackageRequest) (*daemonpb.InstallPackageResponse, error) {
	f.calls = append(f.calls, "InstallPackage")
	f.install = req.GetUri()
	return &daemonpb.InstallPackageResponse{}, f.err
}

func (f *fakeDaemon) RemovePackage(_ context.Context, req *daemonpb.RemovePackageRequest) (*daemonpb.RemovePackageResponse, error) {
	f.calls = append(f.calls, "RemovePackage")
	f.remove = req.GetUri()
	return &daemonpb.RemovePackageResponse{}, f.err
}

func (f *fakeDaemon) ListPackages(context.Context, *daemonpb.ListPackagesRequest) (*daemonpb.ListPackagesResponse, error) {
	f.calls = append(f.calls, "ListPackages")
	return f.packages, f.err
}

// serveFake serves daemon on a fresh unix socket, returning its path.
func serveFake(t *testing.T, daemon *fakeDaemon) string {
	t.Helper()
	// Unix socket paths are limited in length, which t.TempDir can exceed
	dir, err := os.MkdirTemp("", "eagle")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	path := filepath.Join(dir, "eagled.sock")
	ln, err := net.Listen("unix", path)
	if err != nil {
		t.Fatal(err)
	}
	server := grpc.NewServer()
	daemonpb.RegisterDaemonServiceServer(server, daemon)
	daemonpb.RegisterTransferServiceServer(server, daemon)
	go server.Serve(ln)
	t.Cleanup(server.Stop)
	return path
}

// runEagle runs eagle against the socket with args, returning its exit code
// and output.
func runEagle(t *testing.T, socket string, args ...string) (int, string, string) {
	t.Helper()
	var stdout, stderr bytes.Buffer
	code := run(append([]string{"-socket", socket, "-timeout", "5s"}, args...), &stdout, &stderr)
	return code, stdout.String(), stderr.String()
}

// TestConfigureSendsFile checks that configure sends the config file's
// contents.
func TestConfigureSendsFile(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	path := filepath.Join(t.TempDir(), "config.toml")
	content := "[daemon]\nport = 9000\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	code, out, errOut := runEagle(t, socket, "configure", path)
	if code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if daemon.config != content {
		t.Errorf("config sent = %q, want %q", daemon.config, content)
	}
	if !strings.Contains(out, "restarting") {
		t.Errorf("output = %q, want it to say the daemon is restarting", out)
	}
}

// TestConfigureMissingFile checks that a config file that can't be read
// fails without calling the daemon.
func TestConfigureMissingFile(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	code, _, errOut := runEagle(t, socket, "configure", filepath.Join(t.TempDir(), "missing.toml"))
	if code != 1 || !strings.Contains(errOut, "missing.toml") {
		t.Errorf("exit = %d, stderr = %q, want 1 naming the file", code, errOut)
	}
	if len(daemon.calls) > 0 {
		t.Errorf("calls = %v, want none", daemon.calls)
	}
}

// TestSetOrchestrator checks that set-orchestrator sends back the daemon's
// config with only its orchestrator changed.
func TestSetOrchestrator(t *testing.T) {
	for _, tc := range []struct{ host, want string }{
		{"orch.example.com", `orchestrator = "orch.example.com:9100"`},
		{"10.0.0.1", `orchestrator = "10.0.0.1:9100"`},
		{"fd7a::1", `orchestrator = "[fd7a::1]:9100"`},
	} {
		daemon := &fakeDaemon{config: "[daemon]\nport = 9000\nhostname = \"drone\"\norchestrator = \"old:1\"\n"}
		socket := serveFake(t, daemon)
		code, out, errOut := runEagle(t, socket, "set-orchestrator", tc.host, "9100")
		if code != 0 {
			t.Fatalf("%s: exit = %d, stderr = %s", tc.host, code, errOut)
		}
		if got := strings.Join(daemon.calls, ","); got != "GetConfiguration,Configure" {
			t.Errorf("%s: calls = %s, want GetConfiguration,Configure", tc.host, got)
		}
		for _, want := range []string{tc.want, "port = 9000", `hostname = "drone"`} {
			if !strings.Contains(daemon.config, want) {
				t.Errorf("%s: config sent = %q, want it to contain %q", tc.host, daemon.config, want)
			}
		}
		if !strings.Contains(out, "restarting") {
			t.Errorf("%s: output = %q, want it to say the daemon is restarting", tc.host, out)
		}
	}
}

// TestSetOrchestratorBadPort checks that an invalid port is a usage error
// that doesn't call the daemon.
func TestSetOrchestratorBadPort(t *testing.T) {
	for _, port := range []string{"x", "0", "65536"} {
		daemon := &fakeDaemon{}
		socket := serveFake(t, daemon)
		if code, _, _ := runEagle(t, socket, "set-orchestrator", "host", port); code != 2 {
			t.Errorf("port %q: exit = %d, want 2", port, code)
		}
		if len(daemon.calls) > 0 {
			t.Errorf("port %q: calls = %v, want none", port, daemon.calls)
		}
	}
}

// TestRestart checks that restart calls Restart.
func TestRestart(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	if code, _, errOut := runEagle(t, socket, "restart"); code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if len(daemon.calls) != 1 || daemon.calls[0] != "Restart" {
		t.Errorf("calls = %v, want [Restart]", daemon.calls)
	}
}

// TestGetConfig checks that get-config prints the daemon's config as is.
func TestGetConfig(t *testing.T) {
	content := "[daemon]\nport = 9000\n"
	socket := serveFake(t, &fakeDaemon{config: content})
	code, out, errOut := runEagle(t, socket, "get-config")
	if code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if out != content {
		t.Errorf("output = %q, want %q", out, content)
	}
}

// TestStatus checks that status reports whether the daemon is connected.
func TestStatus(t *testing.T) {
	for _, connected := range []bool{true, false} {
		socket := serveFake(t, &fakeDaemon{connected: connected})
		code, out, errOut := runEagle(t, socket, "status")
		if code != 0 {
			t.Fatalf("exit = %d, stderr = %s", code, errOut)
		}
		if got := strings.TrimSpace(out) == "connected"; got != connected {
			t.Errorf("connected = %v: output = %q", connected, out)
		}
	}
}

// TestRestartService checks that restart-service sends the service's name.
func TestRestartService(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	if code, _, errOut := runEagle(t, socket, "restart-service", "100.64.0.2.drone"); code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if daemon.restarted != "100.64.0.2.drone" {
		t.Errorf("restarted = %q, want 100.64.0.2.drone", daemon.restarted)
	}
}

// TestTransfer checks that files and models of several chunks, one chunk and
// none are saved whole by the daemon, under their base name or -name.
func TestTransfer(t *testing.T) {
	src := t.TempDir()
	for _, tc := range []struct {
		command string
		size    int
		args    []string
		saved   string
	}{
		{"transfer-file", 2*chunkSize + 17, nil, "data.bin"},
		{"transfer-model", chunkSize, []string{"-name", "yolo.pt"}, "yolo.pt"},
		{"transfer-file", 0, nil, "data.bin"},
	} {
		daemon := &fakeDaemon{dir: t.TempDir()}
		socket := serveFake(t, daemon)
		content := bytes.Repeat([]byte("eagle"), tc.size/5+1)[:tc.size]
		path := filepath.Join(src, "data.bin")
		if err := os.WriteFile(path, content, 0o644); err != nil {
			t.Fatal(err)
		}
		code, out, errOut := runEagle(t, socket, append(append([]string{tc.command}, tc.args...), path)...)
		if code != 0 {
			t.Fatalf("%s of %d bytes: exit = %d, stderr = %s", tc.command, tc.size, code, errOut)
		}
		if !strings.Contains(out, tc.saved) {
			t.Errorf("%s: output = %q, want it to name %s", tc.command, out, tc.saved)
		}
		got, err := os.ReadFile(filepath.Join(daemon.dir, tc.saved))
		if err != nil {
			t.Fatalf("%s of %d bytes: %v", tc.command, tc.size, err)
		}
		if !bytes.Equal(got, content) {
			t.Errorf("%s of %d bytes: saved %d bytes, want the file", tc.command, tc.size, len(got))
		}
	}
}

// TestTransferRejected checks that a transfer the daemon rejects, like one
// with a bad name, fails with the daemon's reason.
func TestTransferRejected(t *testing.T) {
	socket := serveFake(t, &fakeDaemon{dir: t.TempDir()})
	path := filepath.Join(t.TempDir(), "data.bin")
	if err := os.WriteFile(path, []byte("eagle"), 0o644); err != nil {
		t.Fatal(err)
	}
	code, _, errOut := runEagle(t, socket, "transfer-file", "-name", "../escape", path)
	if code != 1 || !strings.Contains(errOut, "invalid file name") {
		t.Errorf("exit = %d, stderr = %q, want 1 with the daemon's reason", code, errOut)
	}
}

// TestListServicesTable checks that services are printed as a table, with
// their category, status and isolation, followed by the remote daemons, with
// why any can't be reached.
func TestListServicesTable(t *testing.T) {
	daemon := &fakeDaemon{services: daemonpb.ListServicesResponse_builder{
		Services: []*daemonpb.Service{
			daemonpb.Service_builder{
				Name:      "drone",
				Category:  daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE,
				Plugin:    "anafi.toml",
				Uri:       "github.com/example/drivers",
				Isolation: daemonpb.Isolation_ISOLATION_PROCESS,
				Auth:      "admin",
				Running:   true,
			}.Build(),
			daemonpb.Service_builder{
				Name:     "100.64.0.2.yolo",
				Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE,
			}.Build(),
		},
		Remotes: []*daemonpb.Daemon{
			daemonpb.Daemon_builder{Ip: "100.64.0.2", Hostname: "jetson", Os: "linux", Arch: "arm64"}.Build(),
			daemonpb.Daemon_builder{Ip: "100.64.0.3", Error: "connection refused"}.Build(),
		},
	}.Build()}
	socket := serveFake(t, daemon)
	code, out, errOut := runEagle(t, socket, "list-services")
	if code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	want := [][]string{
		{"CATEGORY", "NAME", "PLUGIN", "STATUS", "ISOLATION", "AUTH", "PACKAGE"},
		{"vehicle", "drone", "anafi.toml", "running", "process", "admin", "github.com/example/drivers"},
		{"engine", "100.64.0.2.yolo", "-", "stopped", "-", "-", "-"},
		{},
		{"REMOTE", "HOSTNAME", "PLATFORM", "STATUS"},
		{"100.64.0.2", "jetson", "linux/arm64", "available"},
		{"100.64.0.3", "-", "-", "unavailable:", "connection", "refused"},
	}
	if len(lines) != len(want) {
		t.Fatalf("output = %q, want %d lines", out, len(want))
	}
	for i, fields := range want {
		if got := strings.Fields(lines[i]); strings.Join(got, " ") != strings.Join(fields, " ") {
			t.Errorf("line %d = %q, want fields %q", i, lines[i], fields)
		}
	}
}

// TestListServicesEmpty checks that a daemon without services says so.
func TestListServicesEmpty(t *testing.T) {
	socket := serveFake(t, &fakeDaemon{services: &daemonpb.ListServicesResponse{}})
	if _, out, _ := runEagle(t, socket, "list-services"); strings.TrimSpace(out) != "no services" {
		t.Errorf("output = %q, want no services", out)
	}
}

// TestInstallPackage checks that install-package sends the uri as given.
func TestInstallPackage(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	uri := "https://github.com/example/pkg//plugins@v1.2"
	if code, _, errOut := runEagle(t, socket, "install-package", uri); code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if daemon.install != uri {
		t.Errorf("installed = %q, want %q", daemon.install, uri)
	}
}

// TestRemovePackage checks that remove-package sends the uri.
func TestRemovePackage(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	if code, _, errOut := runEagle(t, socket, "remove-package", "github.com/example/pkg"); code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if daemon.remove != "github.com/example/pkg" {
		t.Errorf("removed = %q, want the uri", daemon.remove)
	}
}

// TestListPackagesTable checks that packages are printed as a table, with
// their plugins sorted.
func TestListPackagesTable(t *testing.T) {
	modified := time.Date(2026, 10, 1, 12, 0, 0, 0, time.Local)
	daemon := &fakeDaemon{packages: daemonpb.ListPackagesResponse_builder{
		Packages: []*daemonpb.Package{
			daemonpb.Package_builder{
				Uri:      "github.com/example/drivers@main",
				Plugins:  map[string][]byte{"sim": nil, "anafi": nil},
				Modified: timestamppb.New(modified),
			}.Build(),
			daemonpb.Package_builder{Uri: "github.com/example/empty"}.Build(),
		},
	}.Build()}
	socket := serveFake(t, daemon)
	code, out, errOut := runEagle(t, socket, "list-packages")
	if code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	want := [][]string{
		{"URI", "MODIFIED", "PLUGINS"},
		{"github.com/example/drivers@main", "2026-10-01", "12:00:00", "anafi,", "sim"},
		{"github.com/example/empty", "-", "-"},
	}
	for i, fields := range want {
		if got := strings.Fields(lines[i]); strings.Join(got, " ") != strings.Join(fields, " ") {
			t.Errorf("line %d = %q, want fields %q", i, lines[i], fields)
		}
	}
}

// TestUsageErrors checks that bad command lines exit 2 without calling the
// daemon.
func TestUsageErrors(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	for _, args := range [][]string{
		{},
		{"nope"},
		{"configure"},
		{"restart", "extra"},
		{"install-package"},
		{"install-package", "-bogus", "uri"},
		{"remove-package", "a", "b"},
		{"restart-service"},
		{"get-config", "extra"},
		{"transfer-file"},
		{"transfer-model", "-bogus", "path"},
	} {
		if code, _, _ := runEagle(t, socket, args...); code != 2 {
			t.Errorf("eagle %q exit = %d, want 2", args, code)
		}
	}
	if len(daemon.calls) > 0 {
		t.Errorf("calls = %v, want none", daemon.calls)
	}
}

// TestDaemonErrors checks that errors from the daemon exit 1, explaining a
// denied call and an unreachable daemon.
func TestDaemonErrors(t *testing.T) {
	socket := serveFake(t, &fakeDaemon{err: status.Error(codes.PermissionDenied, "command is not allowed in state LOCKED")})
	code, _, errOut := runEagle(t, socket, "restart")
	if code != 1 || !strings.Contains(errOut, "not allowed") || !strings.Contains(errOut, "orchestrator") {
		t.Errorf("denied: exit = %d, stderr = %q", code, errOut)
	}

	missing := filepath.Join(t.TempDir(), "none.sock")
	code, _, errOut = runEagle(t, missing, "list-services")
	if code != 1 || !strings.Contains(errOut, "is it running?") {
		t.Errorf("unreachable: exit = %d, stderr = %q", code, errOut)
	}
}
