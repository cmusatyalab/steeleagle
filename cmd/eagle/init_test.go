package main

import (
	tea "charm.land/bubbletea/v2"
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
	if err := os.WriteFile(paths.env, []byte("EAGLED_ARGS=-console\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := writeServiceFiles(paths, "/usr/bin/eagled"); err != nil {
		t.Fatalf("reinstall: %v", err)
	}
	if unit := readFile(t, paths.unit, 0o644); !strings.Contains(unit, "\nExecStart=\"/usr/bin/eagled\" $EAGLED_ARGS\n") {
		t.Errorf("reinstalled unit doesn't start the new eagled:\n%s", unit)
	}
	if env := readFile(t, paths.env, 0o600); env != "EAGLED_ARGS=-console\n" {
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
	if err := writeDefaultConfig(path, "drone-1", "127.0.0.1"); err != nil {
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
	def.Daemon.Bind = "127.0.0.1"
	if !reflect.DeepEqual(cfg, def) {
		t.Errorf("config = %+v, want the default named drone-1, bound to 127.0.0.1 %+v", cfg, def)
	}
}

// TestValidBind checks that only IP addresses of this machine are accepted,
// and that an unspecified address means every interface.
func TestValidBind(t *testing.T) {
	for addr, want := range map[string]string{
		"0.0.0.0":          "",
		"::":               "",
		"127.0.0.1":        "127.0.0.1",
		"::ffff:127.0.0.1": "127.0.0.1",
	} {
		if got, err := validBind(addr); err != nil || got != want {
			t.Errorf("validBind(%q) = %q, %v, want %q", addr, got, err, want)
		}
	}
	for _, addr := range []string{"", "localhost", "127.0.0.1:9000", "999.1.1.1", "192.0.2.123", "fe80::1%lo"} {
		if got, err := validBind(addr); err == nil {
			t.Errorf("validBind(%q) = %q, want an error", addr, got)
		}
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

// writeScript writes an executable shell script with body to a new
// directory, returning its path.
func writeScript(t *testing.T, name, body string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, []byte("#!/bin/sh\n"+body+"\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	return path
}

// TestCheckEagled checks that an eagled that can't run fails with what it
// printed, as with a glibc it needs that the machine lacks.
func TestCheckEagled(t *testing.T) {
	ok := writeScript(t, "eagled", "exit 0")
	if err := checkEagled(context.Background(), ok); err != nil {
		t.Errorf("working eagled: %v", err)
	}

	const loaderError = "libc.so.6: version GLIBC_2.34 not found"
	broken := writeScript(t, "eagled", "echo '"+loaderError+"' >&2; exit 1")
	err := checkEagled(context.Background(), broken)
	if err == nil || !strings.Contains(err.Error(), loaderError) {
		t.Errorf("err = %v, want it to say %q", err, loaderError)
	}
}

// TestWithJournal checks that the tail of the log is added to the error, and
// that the error says how to read the log if it can't be read.
func TestWithJournal(t *testing.T) {
	dir := t.TempDir()
	journalctl := filepath.Join(dir, "journalctl")
	script := "#!/bin/sh\necho \"$@\" > " + filepath.Join(dir, "args") + "\necho boom\n"
	if err := os.WriteFile(journalctl, []byte(script), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dir)
	err := withJournal("eagled failed to start")
	if !strings.Contains(err.Error(), "eagled failed to start") || !strings.Contains(err.Error(), "boom") {
		t.Errorf("err = %q, want the message and the log", err)
	}
	args, _ := os.ReadFile(filepath.Join(dir, "args"))
	if !strings.Contains(string(args), "--user-unit eagled") {
		t.Errorf("journalctl args = %q, want it to read the log by unit", args)
	}

	if err := os.WriteFile(journalctl, []byte("#!/bin/sh\nexit 1\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	err = withJournal("eagled failed to start")
	if !strings.Contains(err.Error(), "journalctl --user-unit eagled") {
		t.Errorf("err = %q, want it to say how to read the log", err)
	}
}

// TestConfirmRoot checks that only a yes goes on, and that a closed input
// doesn't.
func TestConfirmRoot(t *testing.T) {
	for input, want := range map[string]bool{
		"y\n": true, "YES\n": true, " yes \n": true,
		"n\n": false, "\n": false, "maybe\n": false, "": false,
	} {
		var out strings.Builder
		if got := confirmRoot(context.Background(), strings.NewReader(input), &out); got != want {
			t.Errorf("confirmRoot(%q) = %v, want %v", input, got, want)
		}
		if !strings.Contains(out.String(), "as root") {
			t.Errorf("confirmRoot(%q) printed %q, want a warning", input, out.String())
		}
	}
}

// TestConfirmModel checks that the terminal question defaults to no, and
// takes y, n and the selected answer.
func TestConfirmModel(t *testing.T) {
	for _, tc := range []struct {
		keys []tea.KeyPressMsg
		want bool
	}{
		{[]tea.KeyPressMsg{keyEnter}, false},
		{[]tea.KeyPressMsg{keyY}, true},
		{[]tea.KeyPressMsg{keyN}, false},
		{[]tea.KeyPressMsg{{Code: tea.KeyTab}, keyEnter}, true},
		{[]tea.KeyPressMsg{keyCtrlC}, false},
	} {
		m := &confirmModel{question: "Go on?", cursor: 1}
		var cmd tea.Cmd
		for _, k := range tc.keys {
			m.View()
			_, cmd = m.Update(k)
		}
		if !m.answered || m.yes != tc.want || cmd == nil {
			t.Errorf("keys %v: answered = %v, yes = %v, want %v and a command to quit", tc.keys, m.answered, m.yes, tc.want)
		}
	}
}

// fakeGit writes a git that reports version into dir.
func fakeGit(t *testing.T, dir, version string) string {
	t.Helper()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "git")
	if err := os.WriteFile(path, []byte("#!/bin/sh\necho 'git version "+version+"'\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	return path
}

// TestFindGit checks that the git Pixi installed is preferred, that one too
// old to fetch with a filter is skipped, and that the error says how to
// install one.
func TestFindGit(t *testing.T) {
	home := t.TempDir()
	pathDir := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("PATH", pathDir)

	if _, err := findGit(); err == nil || !strings.Contains(err.Error(), "pixi global install git") {
		t.Errorf("no git: err = %v, want it to say how to install one", err)
	}

	old := fakeGit(t, pathDir, "2.25.1")
	if _, err := findGit(); err == nil {
		t.Errorf("git 2.25.1 on the PATH was accepted")
	}

	pixiGit := fakeGit(t, filepath.Join(home, pixiBinDir), "2.56.0")
	if got, err := findGit(); err != nil || got != pixiGit {
		t.Errorf("findGit() = %q, %v, want the Pixi git %q over %q", got, err, pixiGit, old)
	}

	if err := os.Remove(pixiGit); err != nil {
		t.Fatal(err)
	}
	pathGit := fakeGit(t, pathDir, "2.43.0 (Apple Git-154)")
	if got, err := findGit(); err != nil || got != pathGit {
		t.Errorf("findGit() = %q, %v, want the git on the PATH %q", got, err, pathGit)
	}
}
