package daemon

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// testPackageUrl is the url of the fake package written by writeServicePackage.
const testPackageUrl = "github.com/org/plugins"

// newTestServiceDaemon returns a daemon with a package directory holding a
// fake package with engine plugins "detector" and "gcs", and a plugin for
// every other category of service named after its type. The start task records its
// environment in run.txt and runs until it is killed. The daemon's relay, server
// and router are set up like a real daemon's. If the TEST_SERVICE_CLIENT
// environment variable is set, the start task runs it in place of recording
// its environment, recording its calls in calls-{plugin}.txt.
func newTestServiceDaemon(t *testing.T) *Daemon {
	t.Helper()
	t.Setenv("XDG_RUNTIME_DIR", t.TempDir())
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	d := &Daemon{PkgDir: t.TempDir(), Config: &config.DaemonConfig{}, ctx: ctx, log: testLogger(), pluginOut: testOutput()}
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		t.Fatal(err)
	}
	if d.policy, err = policy.NewPolicy(law, policy.WithLogger(testLogger())); err != nil {
		t.Fatal(err)
	}
	if err := d.setupRelay(); err != nil {
		t.Fatal(err)
	}
	go d.server.Serve(d.serverLn)
	t.Cleanup(func() {
		d.relay.Stop()
		d.serverConn.Close()
		d.server.Stop()
	})
	u, err := parsePackageUrl(testPackageUrl)
	if err != nil {
		t.Fatal(err)
	}
	pkg := filepath.Join(d.PkgDir, u.name)
	files := map[string]string{
		"pixi.toml": "[workspace]\nname = 'plugins'\nchannels = []\nplatforms = ['linux-64', 'linux-aarch64', 'osx-arm64']\n\n" +
			"[tasks]\nstart = \"sh run.sh\"\n",
		"run.sh": "[ -n \"$TEST_SERVICE_CLIENT\" ] && exec \"$TEST_SERVICE_CLIENT\" \"calls-$STEELEAGLE_PLUGIN.txt\"\n" +
			"env > run.txt\necho $$ > \"pid-$STEELEAGLE_PLUGIN.txt\"\nexec sleep 60\n",
		"detector" + PluginFileSuffix: "[plugin]\nname = 'Detector'\ntype = 'engine'\n",
		"gcs" + PluginFileSuffix:      "[plugin]\nname = 'GCS'\ntype = 'engine'\n",
	}
	for _, kind := range []string{"monitor", "simulator", "extra"} {
		files[kind+PluginFileSuffix] = "[plugin]\nname = '" + kind + "'\ntype = '" + kind + "'\n"
	}
	if err := os.MkdirAll(pkg, 0755); err != nil {
		t.Fatal(err)
	}
	for name, content := range files {
		if err := os.WriteFile(filepath.Join(pkg, name), []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}
	return d
}

// TestGatherServices ensures that services are gathered from the config
// without being started, that broken services are reported without affecting
// the rest, and are listed with their errors but never started or registered,
// and that only services that were set up have their plugin toml.
func TestGatherServices(t *testing.T) {
	d := newTestServiceDaemon(t)
	detector := config.PluginField{Plugin: "detector", Package: testPackageUrl}
	d.Config.Engines = []config.EngineField{
		{Name: "yolo", Plugin: detector},
		{Name: "yolo", Plugin: detector},
	}
	d.Config.Monitors = []config.ServiceField{{Name: "watch", Plugin: detector}}
	d.Config.Extras = []config.ServiceField{
		{Name: "missing", Plugin: config.PluginField{Plugin: "detector", Package: "github.com/org/missing"}},
	}
	d.Config.Vehicles = []config.VehicleField{{Name: "harpy", Plugin: detector}}

	err := d.gatherServices()
	if err == nil {
		t.Fatal("expected errors for broken services")
	}
	for _, want := range []string{"duplicate service name", `is a "engine" plugin, not "monitor"`,
		"could not read plugin", `is a "engine" plugin, not "driver"`} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("expected error to mention %q, got: %v", want, err)
		}
	}
	all := d.selectServices((*serviceInfo).setUp)
	if len(all) != 1 || all[0].name != "yolo" || all[0].category != daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE {
		t.Fatalf("expected only engine yolo, got %v", all)
	}
	if si := d.findService(daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE, "yolo"); si.running() {
		t.Error("expected gathered service not to be running")
	}
	if vehicles := d.selectServices(func(s *serviceInfo) bool {
		return s.category == daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE && s.setUp()
	}); len(vehicles) != 0 {
		t.Errorf("expected no vehicles to register, got %v", vehicles)
	}

	// Broken services are listed with their errors, in start order
	resp, err := d.ListServices(context.Background(), &daemonpb.ListServicesRequest{})
	if err != nil {
		t.Fatal(err)
	}
	var listed []string
	for _, s := range resp.GetServices() {
		listed = append(listed, s.GetSrv().GetName()+": "+s.GetError())
		if s.GetRunning() {
			t.Errorf("expected %s not running", s.GetSrv().GetName())
		}
	}
	want := []string{
		"yolo: ",
		"yolo: duplicate service name",
		`harpy: plugin "detector" is a "engine" plugin, not "driver"`,
		`watch: plugin "detector" is a "engine" plugin, not "monitor"`,
		"missing: could not read plugin",
	}
	if len(listed) != len(want) {
		t.Fatalf("expected services %q, got %q", want, listed)
	}
	for i := range want {
		if !strings.HasPrefix(listed[i], want[i]) {
			t.Errorf("expected service %q, got %q", want[i], listed[i])
		}
	}
	if missing := resp.GetServices()[4]; missing.GetUrl() != "github.com/org/missing" || missing.GetPlugin() != "detector" {
		t.Errorf("expected the broken service's package and plugin listed, got %v", missing)
	}

	// Broken services can't be restarted
	harpy := []*daemonpb.Service{daemonpb.Service_builder{
		Name: "harpy", Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE,
	}.Build()}
	if _, err := d.RestartServices(context.Background(), daemonpb.RestartServicesRequest_builder{Services: harpy}.Build()); status.Code(err) != codes.FailedPrecondition {
		t.Errorf("expected FailedPrecondition restarting a broken service, got %v", err)
	}

	// Only services that were set up have their plugin toml
	d.configPath = filepath.Join(t.TempDir(), ConfigFileName)
	if err := os.WriteFile(d.configPath, []byte("[daemon]\n"), 0644); err != nil {
		t.Fatal(err)
	}
	cfg, err := d.GetConfiguration(context.Background(), &daemonpb.GetConfigurationRequest{})
	if err != nil {
		t.Fatal(err)
	}
	detectorToml, err := os.ReadFile(filepath.Join(d.PkgDir, "github_com_org_plugins", "detector"+PluginFileSuffix))
	if err != nil {
		t.Fatal(err)
	}
	tomls := cfg.GetPluginTomls()
	if len(tomls) != 1 || string(tomls["engine/yolo"]) != string(detectorToml) {
		t.Errorf("expected only engine/yolo with the detector toml, got %q", tomls)
	}
}

// TestStartStopServices ensures that an engine is started with its plugin
// name, args and iceoryx service in its environment, and that it can be
// stopped and started again.
func TestStartStopServices(t *testing.T) {
	if _, err := exec.LookPath("pixi"); err != nil {
		t.Skip("pixi not installed")
	}
	d := newTestServiceDaemon(t)
	d.Config.Engines = []config.EngineField{{
		Name:   "yolo",
		Plugin: config.PluginField{Plugin: "detector", Package: testPackageUrl, Args: map[string]any{"confidence": 0.5, "label": "a b's \"c\""}},
	}}
	if err := d.gatherServices(); err != nil {
		t.Fatalf("gather failed: %v", err)
	}
	si := d.findService(daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE, "yolo")
	runFile := filepath.Join(d.PkgDir, "github_com_org_plugins", "run.txt")

	for i := range 2 {
		os.Remove(runFile)
		if err := d.startServices(d.selectServices((*serviceInfo).setUp)); err != nil {
			t.Fatalf("run %d: start failed: %v", i, err)
		}
		var run []byte
		for deadline := time.Now().Add(time.Minute); time.Now().Before(deadline); time.Sleep(50 * time.Millisecond) {
			if run, _ = os.ReadFile(runFile); strings.Contains(string(run), IceoryxServiceEnv) {
				break
			}
		}
		for _, want := range []string{
			PluginNameEnv + "=detector",
			PluginArgsEnv + `={"confidence":0.5,"label":"a b's \"c\""}`,
			IceoryxServiceEnv + "=yolo",
		} {
			if !strings.Contains(string(run), want+"\n") {
				t.Errorf("run %d: expected %s in plugin environment", i, want)
			}
		}
		if !si.running() {
			t.Errorf("run %d: expected engine running", i)
		}
		d.stopServices(d.selectServices(nil))
		if si.running() {
			t.Errorf("run %d: expected engine stopped", i)
		}
	}
}

// TestServiceHandlers ensures that services are listed with their state, that
// engines can be restarted whether running or stopped, and that requests for
// unrestartable or unknown services are rejected without acting.
func TestServiceHandlers(t *testing.T) {
	if _, err := exec.LookPath("pixi"); err != nil {
		t.Skip("pixi not installed")
	}
	d := newTestServiceDaemon(t)
	detector := config.PluginField{Plugin: "detector", Package: testPackageUrl}
	d.Config.Engines = []config.EngineField{{Name: "yolo", Plugin: detector}}
	if err := d.gatherServices(); err != nil {
		t.Fatalf("gather failed: %v", err)
	}
	ctx := context.Background()
	yolo := []*daemonpb.Service{daemonpb.Service_builder{
		Name: "yolo", Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE,
	}.Build()}
	assertRunning := func(step string, want bool) {
		t.Helper()
		resp, err := d.ListServices(ctx, &daemonpb.ListServicesRequest{})
		if err != nil || len(resp.GetServices()) != 1 {
			t.Fatalf("%s: expected one service, got %v, %v", step, resp.GetServices(), err)
		}
		s := resp.GetServices()[0]
		if s.GetSrv().GetName() != "yolo" || s.GetPlugin() != "detector" || s.GetUrl() != testPackageUrl {
			t.Errorf("%s: unexpected service description: %v", step, s)
		}
		if s.GetRunning() != want || s.HasUptime() != want || s.GetError() != "" {
			t.Errorf("%s: expected running=%v with uptime and no error, got %v", step, want, s)
		}
	}

	assertRunning("gathered", false)
	if err := d.startServices(d.selectServices((*serviceInfo).setUp)); err != nil {
		t.Fatalf("start failed: %v", err)
	}
	assertRunning("started", true)
	if _, err := d.RestartServices(ctx, daemonpb.RestartServicesRequest_builder{Services: yolo}.Build()); err != nil {
		t.Fatalf("restart failed: %v", err)
	}
	assertRunning("restarted", true)
	d.stopServices(d.selectServices(nil))
	assertRunning("stopped", false)
	// Restarting a stopped service starts it
	pidFile := filepath.Join(d.PkgDir, "github_com_org_plugins", "pid-detector.txt")
	os.Remove(pidFile)
	if _, err := d.RestartServices(ctx, daemonpb.RestartServicesRequest_builder{Services: yolo}.Build()); err != nil {
		t.Fatalf("restart of a stopped service failed: %v", err)
	}
	assertRunning("restarted from stopped", true)

	// A service that exits on its own is listed as exited
	var pid []byte
	for deadline := time.Now().Add(time.Minute); time.Now().Before(deadline); time.Sleep(50 * time.Millisecond) {
		if pid, _ = os.ReadFile(pidFile); strings.HasSuffix(string(pid), "\n") {
			break
		}
	}
	if out, err := exec.Command("kill", strings.TrimSpace(string(pid))).CombinedOutput(); err != nil {
		t.Fatalf("couldn't kill plugin: %v\n%s", err, out)
	}
	deadline := time.Now().Add(10 * time.Second)
	for d.findService(daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE, "yolo").running() && time.Now().Before(deadline) {
		time.Sleep(50 * time.Millisecond)
	}
	resp, err := d.ListServices(ctx, &daemonpb.ListServicesRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if s := resp.GetServices()[0]; s.GetRunning() || !strings.HasPrefix(s.GetError(), "exited") {
		t.Errorf("expected yolo listed as exited, got %v", s)
	}
	d.stopServices(d.selectServices(nil))
	assertRunning("stopped after exiting", false)

	// A bad entry rejects the whole request, so yolo stays stopped
	bad := map[string]struct {
		service *daemonpb.Service
		code    codes.Code
	}{
		"simulator": {daemonpb.Service_builder{Name: "aviary", Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR}.Build(), codes.InvalidArgument},
		"unknown":   {daemonpb.Service_builder{Name: "nope", Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE}.Build(), codes.NotFound},
	}
	for name, tt := range bad {
		req := daemonpb.RestartServicesRequest_builder{Services: append(yolo, tt.service)}.Build()
		if _, err := d.RestartServices(ctx, req); status.Code(err) != tt.code {
			t.Errorf("%s: expected %v, got %v", name, tt.code, err)
		}
	}
	assertRunning("rejected", false)
}

// configureAllCategories configures one service of every category except
// vehicles, plus a second, privileged engine, each on the test package plugin
// for its category. The extra has no auth, so it defaults to unknown.
func configureAllCategories(d *Daemon) {
	field := func(plugin string) config.PluginField {
		return config.PluginField{Plugin: plugin, Package: testPackageUrl}
	}
	d.Config.Simulator = config.ServiceField{Name: "aviary", Auth: config.AuthExternal, Plugin: field("simulator")}
	d.Config.Engines = []config.EngineField{
		{Name: "yolo", Auth: config.AuthExternal, Plugin: field("detector")},
		{Name: "gcs", Auth: config.AuthPrivileged, Plugin: field("gcs")},
	}
	d.Config.Monitors = []config.ServiceField{{Name: "watch", Auth: config.AuthExternal, Plugin: field("monitor")}}
	d.Config.Extras = []config.ServiceField{{Name: "logs", Plugin: field("extra")}}
}

// TestServiceCalls ensures that the daemon serves the listener of every
// category of plugin, and that the law applies to each with the AuthCode of
// its configured auth: external callers can only read, privileged callers can also
// write, and unknown callers can do neither.
func TestServiceCalls(t *testing.T) {
	if _, err := exec.LookPath("pixi"); err != nil {
		t.Skip("pixi not installed")
	}
	client := filepath.Join(t.TempDir(), "service")
	if out, err := exec.Command("go", "build", "-o", client, "./testdata/service").CombinedOutput(); err != nil {
		t.Fatalf("couldn't build fake service: %v\n%s", err, out)
	}
	t.Setenv("TEST_SERVICE_CLIENT", client)
	d := newTestServiceDaemon(t)
	configureAllCategories(d)
	if err := d.gatherServices(); err != nil {
		t.Fatalf("gather failed: %v", err)
	}
	if err := d.startServices(d.selectServices((*serviceInfo).setUp)); err != nil {
		t.Fatalf("start failed: %v", err)
	}
	t.Cleanup(func() { d.stopServices(d.selectServices(nil)) })

	const (
		readOnly = "list=OK\ninstall=PermissionDenied\n"
		// The install passes the law, and fails on its empty url
		readWrite = "list=OK\ninstall=InvalidArgument\n"
		denied    = "list=PermissionDenied\ninstall=PermissionDenied\n"
	)
	want := map[string]string{
		"simulator": readOnly,
		"detector":  readOnly,
		"gcs":       readWrite,
		"monitor":   readOnly,
		"extra":     denied,
	}
	pkg := filepath.Join(d.PkgDir, "github_com_org_plugins")
	for plugin, calls := range want {
		callsFile := filepath.Join(pkg, "calls-"+plugin+".txt")
		var got []byte
		for deadline := time.Now().Add(time.Minute); time.Now().Before(deadline); time.Sleep(50 * time.Millisecond) {
			if got, _ = os.ReadFile(callsFile); len(got) > 0 {
				break
			}
		}
		if string(got) != calls {
			t.Errorf("%s: expected calls %q, got %q", plugin, calls, got)
		}
	}
}

// TestServiceCodes ensures that each plugin is created with the AuthCode of
// its configured auth, defaulting to unknown, and that a service with an
// invalid auth is not set up.
func TestServiceCodes(t *testing.T) {
	d := newTestServiceDaemon(t)
	configureAllCategories(d)
	if err := d.gatherServices(); err != nil {
		t.Fatalf("gather failed: %v", err)
	}

	want := map[string]listener.AuthCode{
		"watch":  listener.ExternalCode,
		"gcs":    listener.PrivilegedCode,
		"aviary": listener.ExternalCode,
		"logs":   listener.UnknownCode,
		"yolo":   listener.ExternalCode,
	}
	got := map[string]listener.AuthCode{}
	for _, s := range d.selectServices(nil) {
		got[s.name] = s.plugin.Code()
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("expected codes %v, got %v", want, got)
	}

	d.Config.Extras[0].Auth = "root"
	if err := d.gatherServices(); err == nil || !strings.Contains(err.Error(), `invalid auth "root"`) {
		t.Errorf("expected invalid auth error, got %v", err)
	}
	if s := d.findService(daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA, "logs"); s == nil || s.setUp() {
		t.Errorf("expected extra with invalid auth listed but not set up, got %v", s)
	}
}

// TestAuthCode ensures that every config auth level maps to its AuthCode,
// with no auth mapping to unknown.
func TestAuthCode(t *testing.T) {
	want := map[config.Auth]listener.AuthCode{
		"":                    listener.UnknownCode,
		config.AuthAdmin:      listener.AdminCode,
		config.AuthPrivileged: listener.PrivilegedCode,
		config.AuthUser:       listener.UserCode,
		config.AuthExternal:   listener.ExternalCode,
		config.AuthUnknown:    listener.UnknownCode,
	}
	for auth, code := range want {
		if got, err := authCode(auth); err != nil || got != code {
			t.Errorf("authCode(%q) = %s, %v, want %s", auth, got, err, code)
		}
	}
	if _, err := authCode("root"); err == nil {
		t.Error("authCode(\"root\") succeeded, want error")
	}
}
