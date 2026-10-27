package daemon

import (
	"errors"
	"os"
	"slices"
	"strings"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"google.golang.org/grpc/codes"
)

// TestRunServices checks that a daemon starts its services in the order of
// engines, vehicles and extras, each with its default or configured auth, and
// with its plugin name, args and, for engines, iceoryx service in its
// environment.
func TestRunServices(t *testing.T) {
	requirePixi(t)
	d := standalone(t,
		testService{name: "x", typ: "extra", plugin: "echo", args: `{ n = 1 }`, auth: "user"},
		testService{name: "v", typ: "vehicle", plugin: "driver"},
		testService{name: "e", typ: "engine", plugin: "detector"},
	)
	d.run()

	resp, err := d.listServices()
	if err != nil {
		t.Fatal(err)
	}
	var names, auths []string
	for _, s := range resp.GetServices() {
		names = append(names, s.GetName())
		auths = append(auths, s.GetAuth())
		if !s.GetRunning() {
			t.Errorf("service %s isn't running", s.GetName())
		}
		if s.GetUri() != testPkg {
			t.Errorf("service %s has uri %q, want %q", s.GetName(), s.GetUri(), testPkg)
		}
	}
	if want := []string{"127.0.0.1.e", "127.0.0.1.v", "127.0.0.1.x"}; !slices.Equal(names, want) {
		t.Errorf("services = %v, want %v", names, want)
	}
	if want := []string{"external", "privileged", "user"}; !slices.Equal(auths, want) {
		t.Errorf("auths = %v, want %v", auths, want)
	}
	if len(resp.GetUnavailable()) != 0 {
		t.Errorf("unavailable = %v, want none", resp.GetUnavailable())
	}
	if resp.GetServices()[0].GetConfig() == nil {
		t.Error("engine has no plugin config")
	}

	if log := readLog(t, "127.0.0.1.x"); !strings.Contains(log, `plugin=echo.plugin.toml args={"n":1} iceoryx=`+"\n") {
		t.Errorf("extra log = %q, want its plugin and args, and no iceoryx service", log)
	}
	if log := readLog(t, "127.0.0.1.e"); !strings.Contains(log, "plugin=detector.plugin.toml args={} iceoryx=127.0.0.1.e\n") {
		t.Errorf("engine log = %q, want its plugin, empty args, and its service name as its iceoryx service", log)
	}

	if !d.connected() {
		t.Error("standalone daemon isn't connected")
	}
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
	for _, name := range []string{"127.0.0.1.e", "127.0.0.1.v", "127.0.0.1.x"} {
		if running, _ := d.pluginRunning(name); running {
			t.Errorf("service %s still running after the daemon stopped", name)
		}
	}
	if _, err := os.Stat(d.socketPath); err == nil {
		t.Error("control socket left behind")
	}
}

// TestFailFast checks that a daemon whose service fails to start stops the
// services it started, and keeps running without them, reporting the failure
// from the service RPCs, while it can still be inspected and reconfigured.
func TestFailFast(t *testing.T) {
	requirePixi(t)
	d := standalone(t, echo("a", "{}"), echo("b", `{ fail = true }`), echo("c", "{}"))
	d.run()

	_, err := d.listServices()
	expectCode(t, err, codes.FailedPrecondition, "127.0.0.1.b")
	_, err = d.client.RestartService(callCtx(t, 5*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.1.a"}.Build())
	expectCode(t, err, codes.FailedPrecondition, "127.0.0.1.b")

	// The service started before the failure was stopped, and the one after
	// it was never started
	if running, ok := d.pluginRunning("127.0.0.1.a"); !ok || running {
		t.Errorf("service a: running = %v, started = %v, want stopped", running, ok)
	}
	if _, ok := d.pluginRunning("127.0.0.1.c"); ok {
		t.Error("service c was started after b failed")
	}

	if _, err := d.client.GetConfiguration(callCtx(t, 5*time.Second), &daemonpb.GetConfigurationRequest{}); err != nil {
		t.Errorf("GetConfiguration() = %v, want nil", err)
	}
	if !d.connected() {
		t.Error("standalone daemon isn't connected")
	}
	// The daemon can be fixed by reconfiguring it
	config := testConfig(t, "solo", "", echo("a", "{}"))
	_, err = d.client.Configure(callCtx(t, 5*time.Second), daemonpb.ConfigureRequest_builder{ConfigToml: config}.Build())
	if err != nil {
		t.Fatal(err)
	}
	if err := d.wait(); !errors.Is(err, ErrRestart) {
		t.Errorf("Run() = %v, want ErrRestart", err)
	}
}

// TestFailFastStop checks that a daemon running without its services stops
// cleanly.
func TestFailFastStop(t *testing.T) {
	requirePixi(t)
	d := standalone(t, echo("b", `{ fail = true }`))
	d.run()
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
}

// TestMissingPackage checks that a daemon whose services use a package that
// isn't installed keeps running without them, like one whose services fail
// to start, so that it can be reconfigured.
func TestMissingPackage(t *testing.T) {
	config := testConfig(t, "solo", "") + `
[[services]]
name = "a"
type = "extra"
[services.plugin]
plugin = "echo"
package = "example.com/not/installed"
`
	n := &testNet{addr: orchAddr, fabric: newFabric()}
	d := newTestDaemon(t, n, config)
	d.run()
	_, err := d.listServices()
	expectCode(t, err, codes.FailedPrecondition, "127.0.0.1.a")
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
}

// TestRunTwice checks that a running daemon can't be run again.
func TestRunTwice(t *testing.T) {
	d := standalone(t)
	d.run()
	if err := d.Run(callCtx(t, 5*time.Second)); err == nil {
		t.Error("second Run() = nil, want error")
	}
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
}
