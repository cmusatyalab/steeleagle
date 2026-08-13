package main_test

import (
	"testing"
	"time"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// TestPersistedConfigSurvivesRestart configures a vehicle, kills eagled, and
// starts a fresh process pointed at the same data directory, confirming
// persist()/loadPersisted() bring the vehicle back running without another
// Configure call.
func TestPersistedConfigSurvivesRestart(t *testing.T) {
	dataDir := t.TempDir()
	const name, driver = "harpy", "mockdriver"

	first := startEagled(t, dataDir)
	writeMockDriver(t, dataDir, driver)

	cfgResp, err := first.Client.Configure(t.Context(), eagledpb.ConfigureRequest_builder{
		ConfigToml: baseConfig(first, freePort(t), name, driver),
	}.Build())
	if err != nil || len(cfgResp.GetVehicles()) != 1 || !cfgResp.GetVehicles()[0].GetOk() {
		t.Fatalf("Configure: resp=%v err=%v", cfgResp, err)
	}

	// RestartDaemon: same data dir, no config change, should just bounce. The
	// RPC reply races the process's own shutdown, so wait for the process to
	// actually exit before starting a second one against the same ports and
	// data dir.
	if _, err := first.Client.RestartDaemon(t.Context(), eagledpb.RestartDaemonRequest_builder{}.Build()); err != nil {
		t.Fatalf("RestartDaemon: %v", err)
	}
	first.WaitExit(t, 10*time.Second)

	// A brand-new eagled process, pointed at the same persisted state (and the
	// plugin dir first's Configure call already staged the driver in;
	// startEagled would otherwise give us a fresh, empty one).
	second := startEagled(t, dataDir)
	second.PluginDir = first.PluginDir // reuse, since applied-config.toml still references it

	status, err := second.Client.GetStatus(t.Context(), eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus on restarted eagled: %v", err)
	}
	if !status.GetConfigured() {
		t.Fatal("expected restarted eagled to already be configured, without another Configure call")
	}
	v := vehicleStatus(t, status, name)
	if !v.GetRunning() {
		t.Fatalf("expected %s to be running again after eagled restart, got %v", name, v)
	}
	if v.GetDriver() != driver {
		t.Errorf("driver = %q, want %q", v.GetDriver(), driver)
	}
}
