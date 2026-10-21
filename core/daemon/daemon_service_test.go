package daemon

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
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
	if ctx.Err() == nil {
		t.Error("expected daemon to stop after configure")
	}
	resp, err = d.GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
	if err != nil || string(resp.GetConfigToml()) != updated {
		t.Errorf("expected updated config, got %q, %v", resp.GetConfigToml(), err)
	}
	if entries, _ := os.ReadDir(filepath.Dir(path)); len(entries) != 1 {
		t.Errorf("expected only the config left in its directory, got %v", entries)
	}
}

// TestRestart ensures that Restart stops the daemon.
func TestRestart(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	d := &Daemon{cancel: cancel, log: testLogger()}
	if _, err := d.Restart(ctx, &daemonpb.RestartRequest{}); err != nil {
		t.Fatalf("restart failed: %v", err)
	}
	if ctx.Err() == nil {
		t.Error("expected daemon to stop after restart")
	}
}
