package main

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

func TestWriteServiceFiles(t *testing.T) {
	paths := newServicePaths(t.TempDir())
	if err := writeServiceFiles(paths, "/opt/steel eagle/eagled"); err != nil {
		t.Fatalf("writeServiceFiles: %v", err)
	}
	unit := readFile(t, paths.unit, 0o644)
	if !strings.Contains(unit, "\nExecStart=\"/opt/steel eagle/eagled\" $EAGLED_ARGS\n") {
		t.Errorf("unit doesn't start the given eagled:\n%s", unit)
	}
	if strings.Contains(unit, unitExecStart) {
		t.Errorf("unit still has the default %q", unitExecStart)
	}
	if env := readFile(t, paths.env, 0o600); env != string(serviceEnv) {
		t.Errorf("env = %q, want the default", env)
	}

	// A reinstall rewrites the unit, but keeps the user's env
	if err := os.WriteFile(paths.env, []byte("STEELEAGLE_AUTH_KEY=secret\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := writeServiceFiles(paths, "/usr/bin/eagled"); err != nil {
		t.Fatalf("reinstall: %v", err)
	}
	if unit := readFile(t, paths.unit, 0o644); !strings.Contains(unit, "\nExecStart=\"/usr/bin/eagled\" $EAGLED_ARGS\n") {
		t.Errorf("reinstalled unit doesn't start the new eagled:\n%s", unit)
	}
	if env := readFile(t, paths.env, 0o600); env != "STEELEAGLE_AUTH_KEY=secret\n" {
		t.Errorf("env = %q, want the user's", env)
	}
}

func TestWriteServiceFilesEscapesSpecifiers(t *testing.T) {
	paths := newServicePaths(t.TempDir())
	if err := writeServiceFiles(paths, "/opt/100%/eagled"); err != nil {
		t.Fatalf("writeServiceFiles: %v", err)
	}
	if unit := readFile(t, paths.unit, 0o644); !strings.Contains(unit, `ExecStart="/opt/100%%/eagled"`) {
		t.Errorf("unit doesn't escape %%:\n%s", unit)
	}
}

func readFile(t *testing.T, path string, perm os.FileMode) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != perm {
		t.Errorf("%s has mode %v, want %v", path, info.Mode().Perm(), perm)
	}
	return string(data)
}

func TestSetAuthKey(t *testing.T) {
	paths := newServicePaths(t.TempDir())
	if err := writeServiceFiles(paths, "/usr/bin/eagled"); err != nil {
		t.Fatal(err)
	}
	path := paths.env
	for _, key := range []string{"tskey-auth-first", "tskey-auth-second"} {
		if err := setAuthKey(path, key); err != nil {
			t.Fatalf("setAuthKey(%q): %v", key, err)
		}
		env := readFile(t, path, 0o600)
		if n := strings.Count(env, authKeyVar+"="); n != 1 {
			t.Errorf("env has %d %s lines, want 1:\n%s", n, authKeyVar, env)
		}
		if !strings.Contains(env, "\n"+authKeyVar+"="+key+"\n") {
			t.Errorf("env doesn't set the key %q:\n%s", key, env)
		}
		// The rest of the file is kept
		if !strings.Contains(env, "EAGLED_ARGS=") {
			t.Errorf("env lost EAGLED_ARGS:\n%s", env)
		}
	}

	// A key without a line of its own yet is appended
	if err := os.WriteFile(path, []byte("EAGLED_ARGS=-console"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := setAuthKey(path, "key"); err != nil {
		t.Fatal(err)
	}
	if env := readFile(t, path, 0o600); env != "EAGLED_ARGS=-console\n"+authKeyVar+"=key\n" {
		t.Errorf("env = %q", env)
	}
	if err := setAuthKey(path, "two\nlines"); err == nil {
		t.Error("setAuthKey accepted a key with a newline")
	}
}

func TestPluginServices(t *testing.T) {
	plugin := func(typ string) []byte {
		return []byte("[plugin]\nname = \"x\"\ntype = \"" + typ + "\"\n")
	}
	packages := []*daemonpb.Package{
		daemonpb.Package_builder{
			Uri: "https://example.com/plugins//defaults/gcs",
			Plugins: map[string][]byte{
				"gcs":     plugin("engine"),
				"monitor": plugin("monitor"),
			},
		}.Build(),
		daemonpb.Package_builder{
			Uri: "https://example.com/plugins//drivers/anafi",
			Plugins: map[string][]byte{
				"anafi": plugin("driver"),
				"sim":   plugin("simulator"),
			},
		}.Build(),
		// A plugin named like another of the same type gets a numbered name
		daemonpb.Package_builder{
			Uri:     "https://example.com/other//gcs",
			Plugins: map[string][]byte{"gcs": plugin("engine")},
		}.Build(),
	}
	got, err := pluginServices(packages)
	if err != nil {
		t.Fatalf("pluginServices: %v", err)
	}
	want := []config.ServiceField{
		{Name: "anafi", Type: config.ServiceVehicle, Plugin: config.PluginField{Plugin: "anafi", Package: "https://example.com/plugins//drivers/anafi"}},
		{Name: "gcs", Type: config.ServiceEngine, Plugin: config.PluginField{Plugin: "gcs", Package: "https://example.com/other//gcs"}},
		{Name: "gcs_2", Type: config.ServiceEngine, Plugin: config.PluginField{Plugin: "gcs", Package: "https://example.com/plugins//defaults/gcs"}},
		{Name: "monitor", Type: config.ServiceExtra, Plugin: config.PluginField{Plugin: "monitor", Package: "https://example.com/plugins//defaults/gcs"}},
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("pluginServices =\n%+v\nwant\n%+v", got, want)
	}

	// The services make a valid config
	cfg := config.DaemonConfig{Daemon: config.DaemonRoot{Port: 9000, Lcs: 9001}, Services: got}
	content, err := cfg.ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := config.ParseDaemonConfigFromBytes(content); err != nil {
		t.Errorf("config of the services is invalid: %v\n%s", err, content)
	}

	bad := []*daemonpb.Package{daemonpb.Package_builder{
		Uri: "https://example.com/bad", Plugins: map[string][]byte{"bad": []byte("not toml [")},
	}.Build()}
	if _, err := pluginServices(bad); err == nil {
		t.Error("pluginServices accepted an invalid plugin file")
	}
}

func TestPluginURI(t *testing.T) {
	want := pluginsRepo + "//drivers/parrot_anafi@" + pluginsRef
	if got := pluginURI("drivers/parrot_anafi"); got != want {
		t.Errorf("pluginURI = %q, want %q", got, want)
	}
}

// TestSystemCommandStrippedPath checks that system tools are found in the
// system directories when they aren't on the PATH.
func TestSystemCommandStrippedPath(t *testing.T) {
	t.Setenv("PATH", t.TempDir())
	cmd := systemCommand("sh", "-c", "true")
	if cmd.Err != nil {
		t.Fatalf("sh not found with an empty PATH: %v", cmd.Err)
	}
	if !filepath.IsAbs(cmd.Path) {
		t.Errorf("path = %q, want an absolute path", cmd.Path)
	}
	if err := cmd.Run(); err != nil {
		t.Errorf("run: %v", err)
	}
}

// TestWriteDefaultConfig checks that the default config replaces an
// existing one, named after the given hostname, which is then suggested
// again.
func TestWriteDefaultConfig(t *testing.T) {
	path := filepath.Join(t.TempDir(), "steeleagle", "config.toml")
	old := "[daemon]\nport = 9100\nhostname = \"old\"\norchestrator = \"homebase:9000\"\n"
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(old), 0o644); err != nil {
		t.Fatal(err)
	}
	if got := defaultHostname(path); got != "old" {
		t.Errorf("defaultHostname = %q, want the configured old", got)
	}
	if err := writeDefaultConfig(path, "drone-1"); err != nil {
		t.Fatalf("writeDefaultConfig: %v", err)
	}
	cfg, err := config.ParseDaemonConfigFromFilepath(path)
	if err != nil {
		t.Fatal(err)
	}
	def, err := config.ParseDaemonConfigFromBytes(defaultConfig)
	if err != nil {
		t.Fatal(err)
	}
	def.Daemon.Hostname = "drone-1"
	if !reflect.DeepEqual(cfg, def) {
		t.Errorf("config = %+v, want the default named drone-1 %+v", cfg, def)
	}
}

// TestDefaultConfigMatchesEagled checks that eagle's copy of the default
// config is the same as eagled's.
func TestDefaultConfigMatchesEagled(t *testing.T) {
	eagled, err := os.ReadFile(filepath.Join("..", "..", "core", "daemon", "defaults", "config.toml"))
	if err != nil {
		t.Fatal(err)
	}
	if string(eagled) != string(defaultConfig) {
		t.Errorf("defaults/config.toml differs from eagled's:\n%s\nwant:\n%s", defaultConfig, eagled)
	}
}

func TestValidHostname(t *testing.T) {
	for name, want := range map[string]bool{
		"drone": true, "Drone-1": true, "a": true, strings.Repeat("a", 63): true,
		"": false, "-drone": false, "drone-": false, "my drone": false, "drone.local": false, "drône": false, strings.Repeat("a", 64): false,
	} {
		if got := validHostname(name); got != want {
			t.Errorf("validHostname(%q) = %v, want %v", name, got, want)
		}
	}
}

// TestWaitReadySafeMode checks that waitReady returns as soon as eagled
// answers that its services failed, rather than waiting for them.
func TestWaitReadySafeMode(t *testing.T) {
	socket := serveFake(t, &fakeDaemon{err: status.Error(codes.FailedPrecondition, "daemon failed to start services: no drone")})
	conn, err := grpc.NewClient("unix://"+socket, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	start := time.Now()
	err = waitReady(context.Background(), conn)
	var safeMode safeModeError
	if !errors.As(err, &safeMode) || !strings.Contains(err.Error(), "no drone") {
		t.Errorf("err = %v, want a safeModeError saying why", err)
	}
	if d := time.Since(start); d > 5*time.Second {
		t.Errorf("took %v, want it to return once eagled answers", d)
	}
}
