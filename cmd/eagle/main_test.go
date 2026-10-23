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
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/durationpb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// fakeDaemon records the calls eagle makes, answering with services and
// packages, and failing every call with err.
type fakeDaemon struct {
	daemonpb.UnimplementedDaemonServiceServer
	err      error
	services *daemonpb.ListServicesResponse
	packages *daemonpb.ListPackagesResponse
	calls    []string
	config   string
	install  *daemonpb.InstallPackageRequest
	remove   string
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
	f.install = req
	return &daemonpb.InstallPackageResponse{}, f.err
}

func (f *fakeDaemon) RemovePackage(_ context.Context, req *daemonpb.RemovePackageRequest) (*daemonpb.RemovePackageResponse, error) {
	f.calls = append(f.calls, "RemovePackage")
	f.remove = req.GetUrl()
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

// TestListServicesTable checks that services are printed as a table, with
// their category, status and uptime, and that unreachable remote daemons are
// reported.
func TestListServicesTable(t *testing.T) {
	daemon := &fakeDaemon{services: daemonpb.ListServicesResponse_builder{
		Services: []*daemonpb.ActiveService{
			daemonpb.ActiveService_builder{
				Srv:     daemonpb.Service_builder{Name: "drone", Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE}.Build(),
				Plugin:  "anafi",
				Url:     "github.com/example/drivers",
				Running: true,
				Uptime:  durationpb.New(90*time.Second + 300*time.Millisecond),
			}.Build(),
			daemonpb.ActiveService_builder{
				Srv:   daemonpb.Service_builder{Name: "yolo", Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE}.Build(),
				Error: "plugin exited",
			}.Build(),
		},
		Unavailable: []string{"100.64.0.2"},
	}.Build()}
	socket := serveFake(t, daemon)
	code, out, errOut := runEagle(t, socket, "list-services")
	if code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	want := [][]string{
		{"CATEGORY", "NAME", "PLUGIN", "STATUS", "UPTIME", "PACKAGE", "ERROR"},
		{"vehicle", "drone", "anafi", "running", "1m30s", "github.com/example/drivers", "-"},
		{"engine", "yolo", "-", "stopped", "-", "-", "plugin", "exited"},
	}
	for i, fields := range want {
		if got := strings.Fields(lines[i]); strings.Join(got, " ") != strings.Join(fields, " ") {
			t.Errorf("line %d = %q, want fields %q", i, lines[i], fields)
		}
	}
	if !strings.Contains(out, "could not reach remote daemons: 100.64.0.2") {
		t.Errorf("output = %q, want the unreachable daemon", out)
	}
}

// TestListServicesEmpty checks that a daemon without services says so.
func TestListServicesEmpty(t *testing.T) {
	socket := serveFake(t, &fakeDaemon{services: &daemonpb.ListServicesResponse{}})
	if _, out, _ := runEagle(t, socket, "list-services"); strings.TrimSpace(out) != "no services" {
		t.Errorf("output = %q, want no services", out)
	}
}

// TestInstallPackage checks that install-package sends the URL, and the tag
// only when one is given.
func TestInstallPackage(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	if code, _, errOut := runEagle(t, socket, "install-package", "-tag", "v1.2", "github.com/example/pkg"); code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if daemon.install.GetUrl() != "github.com/example/pkg" || daemon.install.GetTag() != "v1.2" {
		t.Errorf("install = %v, want the URL with tag v1.2", daemon.install)
	}
	if code, _, errOut := runEagle(t, socket, "install-package", "github.com/example/other"); code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if daemon.install.HasTag() {
		t.Errorf("install without -tag = %v, want no tag", daemon.install)
	}
}

// TestRemovePackage checks that remove-package sends the URL.
func TestRemovePackage(t *testing.T) {
	daemon := &fakeDaemon{}
	socket := serveFake(t, daemon)
	if code, _, errOut := runEagle(t, socket, "remove-package", "github.com/example/pkg"); code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	if daemon.remove != "github.com/example/pkg" {
		t.Errorf("removed = %q, want the URL", daemon.remove)
	}
}

// TestListPackagesTable checks that packages are printed as a table, with
// their plugins sorted.
func TestListPackagesTable(t *testing.T) {
	modified := time.Date(2026, 10, 1, 12, 0, 0, 0, time.Local)
	daemon := &fakeDaemon{packages: daemonpb.ListPackagesResponse_builder{
		Packages: []*daemonpb.Package{
			daemonpb.Package_builder{
				Url:      "github.com/example/drivers",
				Tag:      "main",
				Plugins:  map[string][]byte{"sim": nil, "anafi": nil},
				Modified: timestamppb.New(modified),
			}.Build(),
			daemonpb.Package_builder{Url: "github.com/example/empty"}.Build(),
		},
	}.Build()}
	socket := serveFake(t, daemon)
	code, out, errOut := runEagle(t, socket, "list-packages")
	if code != 0 {
		t.Fatalf("exit = %d, stderr = %s", code, errOut)
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	want := [][]string{
		{"URL", "TAG", "MODIFIED", "PLUGINS"},
		{"github.com/example/drivers", "main", "2026-10-01", "12:00:00", "anafi,", "sim"},
		{"github.com/example/empty", "-", "-", "-"},
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
		{"install-package", "-bogus", "url"},
		{"remove-package", "a", "b"},
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
