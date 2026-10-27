package daemon

import (
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TestRestartService checks that a service that died can be restarted, that
// a running one is restarted with a new process, and that an unknown one
// can't be.
func TestRestartService(t *testing.T) {
	requirePixi(t)
	d := standalone(t, echo("a", "{}"), echo("crash", `{ exit_after_ms = 1500 }`))
	d.run()
	const crash = "127.0.0.1.crash"

	// The crashing service dies after it starts
	eventually(t, 10*time.Second, func() error {
		resp, err := d.listServices()
		if err != nil {
			return err
		}
		if running(resp)[crash] {
			return errors.New("service still running")
		}
		return nil
	})
	_, err := d.client.RestartService(callCtx(t, 30*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: crash}.Build())
	if err != nil {
		t.Fatal(err)
	}
	resp, err := d.listServices()
	if err != nil {
		t.Fatal(err)
	}
	if !running(resp)[crash] {
		t.Error("restarted service isn't running")
	}
	// Restarts write to the same log
	if log := readLog(t, crash); strings.Count(log, "plugin=echo.plugin.toml") != 2 {
		t.Errorf("log = %q, want a line from each run", log)
	}

	// A running service is restarted
	_, err = d.client.RestartService(callCtx(t, 30*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.1.a"}.Build())
	if err != nil {
		t.Fatal(err)
	}
	if log := readLog(t, "127.0.0.1.a"); strings.Count(log, "plugin=echo.plugin.toml") != 2 {
		t.Errorf("log = %q, want a line from each run", log)
	}
	if running, _ := d.pluginRunning("127.0.0.1.a"); !running {
		t.Error("restarted service isn't running")
	}

	_, err = d.client.RestartService(callCtx(t, 5*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.1.nope"}.Build())
	expectCode(t, err, codes.NotFound, "127.0.0.1.nope")
	// Services are only known by their qualified names
	_, err = d.client.RestartService(callCtx(t, 5*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "a"}.Build())
	expectCode(t, err, codes.NotFound)
}

// TestRestartServiceConcurrent checks that concurrent restarts and listings
// of the same service are serialized, leaving it running.
func TestRestartServiceConcurrent(t *testing.T) {
	requirePixi(t)
	d := standalone(t, echo("a", "{}"))
	d.run()
	errs := make(chan error, 8)
	for i := range cap(errs) {
		go func() {
			if i%2 == 0 {
				_, err := d.client.RestartService(callCtx(t, 60*time.Second),
					daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.1.a"}.Build())
				errs <- err
			} else {
				_, err := d.client.ListServices(callCtx(t, 60*time.Second), &daemonpb.ListServicesRequest{})
				errs <- err
			}
		}()
	}
	for range cap(errs) {
		if err := <-errs; err != nil {
			t.Error(err)
		}
	}
	if running, _ := d.pluginRunning("127.0.0.1.a"); !running {
		t.Error("service isn't running after concurrent restarts")
	}
}

// TestRestart checks that Restart answers, then stops the daemon for a
// restart.
func TestRestart(t *testing.T) {
	requirePixi(t)
	d := standalone(t, echo("a", "{}"))
	d.run()
	if _, err := d.client.Restart(callCtx(t, 5*time.Second), &daemonpb.RestartRequest{}); err != nil {
		t.Fatal(err)
	}
	if err := d.wait(); !errors.Is(err, ErrRestart) {
		t.Errorf("Run() = %v, want ErrRestart", err)
	}
	if running, _ := d.pluginRunning("127.0.0.1.a"); running {
		t.Error("service still running after restart")
	}
}

// TestConfigure checks that a config is only replaced by a valid one, which
// restarts the daemon, and that it is replaced atomically.
func TestConfigure(t *testing.T) {
	d := standalone(t)
	d.run()
	before, err := os.ReadFile(d.configPath)
	if err != nil {
		t.Fatal(err)
	}
	resp, err := d.client.GetConfiguration(callCtx(t, 5*time.Second), &daemonpb.GetConfigurationRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if string(resp.GetConfigToml()) != string(before) {
		t.Errorf("GetConfiguration() = %q, want %q", resp.GetConfigToml(), before)
	}

	invalid := map[string]string{
		"bad toml":        "[daemon",
		"unknown type":    "[[services]]\nname = \"a\"\ntype = \"nope\"\n",
		"no package":      "[[services]]\nname = \"a\"\ntype = \"extra\"\n[services.plugin]\nplugin = \"echo\"\n",
		"duplicate names": testConfig(t, "solo", "", echo("a", "{}"), echo("a", "{}")),
	}
	for name, config := range invalid {
		_, err := d.client.Configure(callCtx(t, 5*time.Second), daemonpb.ConfigureRequest_builder{ConfigToml: config}.Build())
		if status.Code(err) != codes.InvalidArgument {
			t.Errorf("Configure() with %s = %v, want InvalidArgument", name, err)
		}
	}
	if after, _ := os.ReadFile(d.configPath); string(after) != string(before) {
		t.Errorf("invalid configs replaced the config with %q", after)
	}
	if _, err := d.client.GetConfiguration(callCtx(t, 5*time.Second), &daemonpb.GetConfigurationRequest{}); err != nil {
		t.Errorf("daemon stopped serving after invalid configs: %v", err)
	}

	config := testConfig(t, "renamed", "", echo("a", "{}"))
	if _, err := d.client.Configure(callCtx(t, 5*time.Second), daemonpb.ConfigureRequest_builder{ConfigToml: config}.Build()); err != nil {
		t.Fatal(err)
	}
	if err := d.wait(); !errors.Is(err, ErrRestart) {
		t.Errorf("Run() = %v, want ErrRestart", err)
	}
	if after, _ := os.ReadFile(d.configPath); string(after) != config {
		t.Errorf("config = %q, want %q", after, config)
	}
	entries, _ := os.ReadDir(filepath.Dir(d.configPath))
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".config-") {
			t.Errorf("temporary config %s left behind", e.Name())
		}
	}
}

// TestPopulateServices checks the services a daemon sets up from its config:
// the simulator first, then each service with its qualified name, default or
// configured auth, isolation, and plugin, where simulated services ignore
// their plugin's args and isolation.
func TestPopulateServices(t *testing.T) {
	d := newIdleDaemon(t, childAddr, testConfig(t, "child", ""))
	sim := installSimulator(t)
	d.Config = &config.DaemonConfig{
		Simulator: config.SimulatorField{Package: sim, Args: map[string]any{"vehicles": []any{"v"}}},
		Services: []config.ServiceField{
			{Name: "e", Type: config.ServiceEngine, Plugin: config.PluginField{
				Plugin: "detector", Package: testPkg, Isolation: config.IsolationSandbox}},
			{Name: "v", Type: config.ServiceVehicle, Simulate: true, Plugin: config.PluginField{
				Plugin: "sim_vehicle", Package: sim, Isolation: "docker.io/x:1", Args: map[string]any{"ignored": true}}},
			{Name: "x", Type: config.ServiceExtra, Auth: config.AuthAdmin, Plugin: config.PluginField{
				Plugin: "echo" + PluginFileSuffix, Package: testPkg, Isolation: "docker.io/library/alpine:3",
				Args: map[string]any{"n": 1}}},
		},
	}
	if err := d.populateServices(); err != nil {
		t.Fatal(err)
	}

	var names []string
	for _, s := range d.services {
		names = append(names, s.name)
		if d.lookup[s.name] != s {
			t.Errorf("service %s isn't in the lookup table", s.name)
		}
	}
	if want := []string{"127.0.0.2.simulator", "127.0.0.2.e", "127.0.0.2.v", "127.0.0.2.x"}; !slices.Equal(names, want) {
		t.Fatalf("services = %v, want %v", names, want)
	}
	simulator, e, v, x := d.services[0], d.services[1], d.services[2], d.services[3]

	if simulator.category != daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR ||
		simulator.pluginName != "" || simulator.args != `{"vehicles":["v"]}` || simulator.uri != sim {
		t.Errorf("simulator = %+v, want the simulator package, with its args and no plugin", simulator)
	}
	if e.auth != listener.ExternalCode || e.isolation != daemonpb.Isolation_ISOLATION_SANDBOX ||
		e.pluginName != "detector.plugin.toml" || e.config == nil || e.config.Engine == nil || e.args != "{}" {
		t.Errorf("engine = %+v, want an external, sandboxed detector with its config", e)
	}
	if v.auth != listener.PrivilegedCode || !v.simulated || v.uri != sim || v.pluginName != "sim_vehicle.plugin.toml" ||
		v.args != "{}" || v.isolation != daemonpb.Isolation_ISOLATION_PROCESS || v.container != "" || v.config == nil {
		t.Errorf("vehicle = %+v, want a privileged simulated vehicle, ignoring its plugin's args and isolation", v)
	}
	if x.auth != listener.AdminCode || x.isolation != daemonpb.Isolation_ISOLATION_CONTAINER ||
		x.container != "docker.io/library/alpine:3" || x.pluginName != "echo.plugin.toml" || x.args != `{"n":1}` ||
		!strings.HasSuffix(x.path, getPackageDir(testPkg)) {
		t.Errorf("extra = %+v, want an admin echo plugin in a container", x)
	}
}

// TestPopulateServicesErrors checks that services can't be set up from
// packages or plugins that aren't installed, or as simulated without a
// simulator.
func TestPopulateServicesErrors(t *testing.T) {
	// Creating a daemon commits the test package
	newIdleDaemon(t, orchAddr, testConfig(t, "orch", ""))
	sim := installSimulator(t)
	tests := map[string]config.DaemonConfig{
		"missing package": {Services: []config.ServiceField{{Name: "x", Type: config.ServiceExtra,
			Plugin: config.PluginField{Plugin: "echo", Package: "example.com/missing"}}}},
		"missing plugin": {Services: []config.ServiceField{{Name: "x", Type: config.ServiceExtra,
			Plugin: config.PluginField{Plugin: "nope", Package: testPkg}}}},
		"plugin outside the package": {Services: []config.ServiceField{{Name: "x", Type: config.ServiceExtra,
			Plugin: config.PluginField{Plugin: "../" + getPackageDir(sim) + "/sim_vehicle", Package: testPkg}}}},
		"missing simulator package": {Simulator: config.SimulatorField{Package: "example.com/missing"}},
		"no simulator": {Services: []config.ServiceField{{Name: "v", Type: config.ServiceVehicle, Simulate: true,
			Plugin: config.PluginField{Plugin: "sim_vehicle", Package: sim}}}},
	}
	for name, c := range tests {
		d := &Daemon{Config: &c, lookup: map[string]*daemonService{}, log: testLogger(), netAddr: orchAddr}
		if err := d.populateServices(); err == nil {
			t.Errorf("populateServices() with %s = nil, want error", name)
		}
	}
}

// TestEncodeArgs checks that args are encoded as a JSON object, which is
// empty without any.
func TestEncodeArgs(t *testing.T) {
	tests := []struct {
		args map[string]any
		want string
	}{
		{nil, "{}"},
		{map[string]any{}, "{}"},
		{map[string]any{"ip": "10.0.0.1", "n": int64(2), "nested": map[string]any{"a": []any{true}}},
			`{"ip":"10.0.0.1","n":2,"nested":{"a":[true]}}`},
	}
	for _, tt := range tests {
		got, err := encodeArgs(tt.args)
		if err != nil || got != tt.want {
			t.Errorf("encodeArgs(%v) = %q, %v, want %q", tt.args, got, err, tt.want)
		}
	}
}

// TestGetPackageDir checks that package uris map to distinct flat directory
// names.
func TestGetPackageDir(t *testing.T) {
	tests := map[string]string{
		"github.com/org/repo":           "github_com_org_repo",
		"github.com/org/repo//sub":      "github_com_org_repo__sub",
		"github.com/org/repo//sub@v1.0": "github_com_org_repo__sub@v1_0",
		"https://host:8080/repo":        "https___host_8080_repo",
	}
	for uri, want := range tests {
		got := getPackageDir(uri)
		if got != want {
			t.Errorf("getPackageDir(%q) = %q, want %q", uri, got, want)
		}
		if filepath.Base(got) != got {
			t.Errorf("getPackageDir(%q) = %q, which isn't a single path element", uri, got)
		}
	}
}

// TestVehicleEngineMap checks that vehicles are given every local and remote
// engine, and nothing else.
func TestVehicleEngineMap(t *testing.T) {
	engine := daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE
	locals := []*daemonService{
		{name: "l.e", category: engine, config: &config.PluginConfig{}},
		{name: "l.v", category: daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE},
		{name: "l.x", category: daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA},
	}
	remotes := []*daemonService{
		{name: "r.e", category: engine},
		{name: "r.s", category: daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR},
	}
	m := getVehicleEngineMap(locals, remotes)
	if len(m) != 2 || m["l.e"] == nil || !m["l.e"].Local || m["l.e"].Config != locals[0].config ||
		m["r.e"] == nil || m["r.e"].Local {
		t.Errorf("engine map = %+v, want local l.e and remote r.e", m)
	}
	if m := getVehicleEngineMap(nil, nil); len(m) != 0 {
		t.Errorf("engine map without services = %+v, want empty", m)
	}
}

// TestRestartVehicle checks that a vehicle service can be restarted, and
// that the vehicle is reachable through the daemon after each start.
func TestRestartVehicle(t *testing.T) {
	requirePixi(t)
	d := standalone(t, testService{name: "v", typ: "vehicle", plugin: "driver"})
	d.run()
	const v = "127.0.0.1.v"
	for i := range 3 {
		if i > 0 {
			_, err := d.client.RestartService(callCtx(t, 30*time.Second),
				daemonpb.RestartServiceRequest_builder{ServiceNames: v}.Build())
			if err != nil {
				t.Fatalf("restart %d: %v", i, err)
			}
		}
		resp, err := d.listServices()
		if err != nil {
			t.Fatal(err)
		}
		if !running(resp)[v] {
			t.Errorf("run %d: vehicle isn't running", i)
		}
		_, err = vehiclepb.NewSafetyServiceClient(d.ctl).GetFailsafeState(routed(t, v),
			&vehiclepb.GetFailsafeStateRequest{})
		if err != nil {
			t.Errorf("run %d: couldn't reach the vehicle: %v", i, err)
		}
	}
}
