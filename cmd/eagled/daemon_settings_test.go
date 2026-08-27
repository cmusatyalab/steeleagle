package main_test

import (
	"fmt"
	"testing"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// daemonWideConfig is a minimal, vehicle-free config document, for testing
// daemon-wide settings behavior in isolation from vehicle start/stop.
func daemonWideConfig(hostname, swarmAddr string) string {
	return fmt.Sprintf(`
port-base = 9000
hostname = %q

[backend.swarm-controller]
address = %q
`, hostname, swarmAddr)
}

// TestConfigureDaemonSettingsAppliedOnlyOnFirstCall exercises
// ConfigureResponse.daemon_settings_applied/daemon_settings_diverged across
// three Configure calls to the same daemon: the first establishes daemon-wide
// settings, a second call with identical settings is a silent no-op (neither
// applied nor diverged), and a third call with a different setting is
// reported as diverged rather than silently dropped.
func TestConfigureDaemonSettingsAppliedOnlyOnFirstCall(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()

	resp1, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: daemonWideConfig("test-daemon", "127.0.0.1:1"),
	}.Build())
	if err != nil {
		t.Fatalf("Configure (first call): %v", err)
	}
	if !resp1.GetDaemonSettingsApplied() {
		t.Error("expected daemon_settings_applied=true on the first Configure call")
	}
	if resp1.GetDaemonSettingsDiverged() {
		t.Error("expected daemon_settings_diverged=false on the first Configure call")
	}

	resp2, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: daemonWideConfig("test-daemon", "127.0.0.1:1"),
	}.Build())
	if err != nil {
		t.Fatalf("Configure (identical second call): %v", err)
	}
	if resp2.GetDaemonSettingsApplied() {
		t.Error("expected daemon_settings_applied=false on a later call")
	}
	if resp2.GetDaemonSettingsDiverged() {
		t.Error("expected daemon_settings_diverged=false when the later call's settings match what's active")
	}

	resp3, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: daemonWideConfig("test-daemon", "127.0.0.1:2"), // different swarm-controller address
	}.Build())
	if err != nil {
		t.Fatalf("Configure (diverging third call): %v", err)
	}
	if resp3.GetDaemonSettingsApplied() {
		t.Error("expected daemon_settings_applied=false on a later call")
	}
	if !resp3.GetDaemonSettingsDiverged() {
		t.Error("expected daemon_settings_diverged=true when the later call's settings differ from what's active")
	}

	// The originally-configured address should still be what's active --
	// the diverging third call must not have taken effect.
	status, err := inst.Client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if got := status.GetConfig().GetSwarmControllerAddress(); got != "127.0.0.1:1" {
		t.Errorf("swarm controller address = %q, want unchanged %q", got, "127.0.0.1:1")
	}
}

// TestConfigureHostnameFrozenAfterFirstCall verifies that hostname, like
// every other daemon-wide setting, is only ever established from a fresh
// daemon's first Configure call: a later call with a different hostname
// doesn't change it, and shows up as diverged rather than silently
// re-joining under the new name.
func TestConfigureHostnameFrozenAfterFirstCall(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()

	if _, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: daemonWideConfig("first-name", "127.0.0.1:1"),
	}.Build()); err != nil {
		t.Fatalf("Configure (first call): %v", err)
	}

	resp, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: daemonWideConfig("second-name", "127.0.0.1:1"),
	}.Build())
	if err != nil {
		t.Fatalf("Configure (second call, different hostname): %v", err)
	}
	if !resp.GetDaemonSettingsDiverged() {
		t.Error("expected daemon_settings_diverged=true when hostname differs from what's active")
	}

	status, err := inst.Client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if got := status.GetConfig().GetDaemonName(); got != "first-name" {
		t.Errorf("daemon name = %q, want unchanged %q (hostname must be frozen after the first call)", got, "first-name")
	}
}
