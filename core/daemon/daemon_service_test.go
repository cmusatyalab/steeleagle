package daemon

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/adrg/xdg"
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util/network"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TestConfiguration ensures that Configure replaces the config on disk and
// stops the daemon, that GetConfiguration returns it, and that an invalid
// config leaves the current one in place.
func TestConfiguration(t *testing.T) {
	path := filepath.Join(t.TempDir(), ConfigFileName)
	original, err := os.ReadFile("../../config/examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, original, 0644); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	d := &Daemon{configPath: path, cancel: cancel, log: testLogger()}

	resp, err := d.GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
	if err != nil || string(resp.GetConfigToml()) != string(original) {
		t.Fatalf("expected original config, got %q, %v", resp.GetConfigToml(), err)
	}

	// An invalid config is rejected without stopping the daemon
	_, err = d.Configure(ctx, daemonpb.ConfigureRequest_builder{ConfigToml: "[daemon"}.Build())
	if status.Code(err) != codes.InvalidArgument {
		t.Errorf("expected InvalidArgument, got %v", err)
	}
	if ctx.Err() != nil {
		t.Error("expected daemon to keep running after an invalid config")
	}

	updated := "[daemon]\nhostname = 'updated'\n"
	if _, err := d.Configure(ctx, daemonpb.ConfigureRequest_builder{ConfigToml: updated}.Build()); err != nil {
		t.Fatalf("configure failed: %v", err)
	}
	if ctx.Err() == nil || !d.restart.Load() {
		t.Error("expected daemon to stop for a restart after configure")
	}
	resp, err = d.GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
	if err != nil || string(resp.GetConfigToml()) != updated {
		t.Errorf("expected updated config, got %q, %v", resp.GetConfigToml(), err)
	}
	if entries, _ := os.ReadDir(filepath.Dir(path)); len(entries) != 1 {
		t.Errorf("expected only the config left in its directory, got %v", entries)
	}
}

// TestRestart ensures that Restart stops the daemon for a restart.
func TestRestart(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	d := &Daemon{cancel: cancel, log: testLogger()}
	if _, err := d.Restart(ctx, &daemonpb.RestartRequest{}); err != nil {
		t.Fatalf("restart failed: %v", err)
	}
	if ctx.Err() == nil || !d.restart.Load() {
		t.Error("expected daemon to stop for a restart after restart")
	}
}

// freePort returns a local TCP port that nothing listens on.
func freePort(t *testing.T) int {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	return ln.Addr().(*net.TCPAddr).Port
}

// TestRunRestart ensures that a restart stops a running daemon, closing
// everything it started, so that Run returns ErrRestart and the daemon's port
// is free for the daemon to be started again.
func TestRunRestart(t *testing.T) {
	if network.Tailscale {
		t.Skip("needs the host network of the notailscale build tag")
	}
	t.Setenv("XDG_DATA_HOME", t.TempDir())
	t.Setenv("XDG_RUNTIME_DIR", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)
	port := freePort(t)
	path := filepath.Join(t.TempDir(), ConfigFileName)
	content := fmt.Sprintf("[daemon]\nport = %d\nlcs = %d\nhostname = 'restart-%d'\n", port, freePort(t), os.Getpid())
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	d, err := NewDaemon(WithConfigPath(path), WithLogger(testLogger()))
	if err != nil {
		t.Fatal(err)
	}
	errc := make(chan error, 1)
	go func() { errc <- d.Run(context.Background()) }()

	client := daemonpb.NewDaemonServiceClient(dial(t, fmt.Sprintf("127.0.0.1:%d", port)))
	waitFor(t, "the daemon to serve", func() bool {
		ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
		defer cancel()
		_, err := client.ListServices(ctx, &daemonpb.ListServicesRequest{})
		return err == nil
	})
	if _, err := d.Restart(context.Background(), &daemonpb.RestartRequest{}); err != nil {
		t.Fatalf("restart failed: %v", err)
	}
	select {
	case err := <-errc:
		if !errors.Is(err, ErrRestart) {
			t.Errorf("expected Run to return ErrRestart, got %v", err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("daemon didn't stop after restart")
	}
	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		t.Errorf("expected the daemon port free after restart, got %v", err)
	} else {
		ln.Close()
	}
}

// TestNewDaemonDefaultConfigPath ensures that, without a config path, the
// daemon writes its default config to the config directory and reads it from
// there, rather than the data directory.
func TestNewDaemonDefaultConfigPath(t *testing.T) {
	configHome, dataHome := t.TempDir(), t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", configHome)
	t.Setenv("XDG_DATA_HOME", dataHome)
	t.Setenv("XDG_RUNTIME_DIR", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)

	d, err := NewDaemon(WithLogger(testLogger()))
	if err != nil {
		t.Fatal(err)
	}
	want := filepath.Join(configHome, "steeleagle", ConfigFileName)
	if d.configPath != want {
		t.Errorf("config path = %s, want %s", d.configPath, want)
	}
	content, err := os.ReadFile(want)
	if err != nil {
		t.Fatalf("default config not written to the config directory: %v", err)
	}
	if string(content) != string(DefaultConfig) {
		t.Errorf("config written = %q, want the default config", content)
	}
	if _, err := os.Stat(filepath.Join(dataHome, "steeleagle", ConfigFileName)); err == nil {
		t.Error("config written to the data directory")
	}

	// A config already in the config directory is read, not replaced
	custom := "[daemon]\nport = 9100\nlcs = 9101\nhostname = 'custom'\n"
	if err := os.WriteFile(want, []byte(custom), 0644); err != nil {
		t.Fatal(err)
	}
	d, err = NewDaemon(WithLogger(testLogger()))
	if err != nil {
		t.Fatal(err)
	}
	if d.Config.Daemon.Hostname != "custom" || d.Config.Daemon.Port != 9100 {
		t.Errorf("config = %+v, want the one in the config directory", d.Config.Daemon)
	}
}
