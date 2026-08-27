package main_test

import (
	"fmt"
	"testing"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// configWithArgs mirrors baseConfig but lets the driver's args vary, so a
// second Configure call for the same vehicle name is distinguishable from the
// first without changing anything that would actually break mockdriver
// (which ignores its args entirely).
func configWithArgs(inst *eagledInstance, vehiclePort int, vehicleName, driverName, arg string) string {
	return fmt.Sprintf(`
port-base = %d
plugin-dir = %q
hostname = "test-daemon"

[backend.swarm-controller]
address = "127.0.0.1:1"

[[vehicles]]
name = %q
[vehicles.driver]
name = %q
args = [%q]
`, vehiclePort, inst.PluginDir, vehicleName, driverName, arg)
}

// getStatus is a small convenience wrapper around GetStatus for tests that
// call it more than once.
func getStatus(t *testing.T, inst *eagledInstance) *eagledpb.GetStatusResponse {
	t.Helper()
	status, err := inst.Client.GetStatus(t.Context(), eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	return status
}

// TestConfigureReconfiguresStoppedVehicle verifies that reconfiguring a
// known, stopped vehicle is reported via VehicleResult.reconfigured, and
// distinguished from configuring a vehicle for the first time.
func TestConfigureReconfiguresStoppedVehicle(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()
	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)
	port := freePort(t)

	first := configureOne(t, inst, configWithArgs(inst, port, name, driver, "--a"))
	if !first.GetOk() || first.GetReconfigured() {
		t.Fatalf("expected first Configure of %s to succeed and not be a reconfigure, got %v", name, first)
	}

	if _, err := inst.Client.StopVehicles(ctx, eagledpb.StopVehiclesRequest_builder{Names: []string{name}}.Build()); err != nil {
		t.Fatalf("StopVehicles: %v", err)
	}

	second := configureOne(t, inst, configWithArgs(inst, port, name, driver, "--b"))
	if !second.GetOk() {
		t.Fatalf("expected reconfigure of stopped %s to succeed, got %v", name, second)
	}
	if !second.GetReconfigured() {
		t.Error("expected VehicleResult.reconfigured=true when reconfiguring an already-known, stopped vehicle")
	}
	if second.GetRestartRequired() {
		t.Error("expected VehicleResult.restart_required=false: a stopped vehicle is actually restarted under the new config, not left running on the old one")
	}
}

// TestConfigureRunningVehicleSetsRestartRequired verifies that reconfiguring
// a currently-running vehicle leaves the running process alone (rather than
// restarting it out from under whatever it's doing), reports
// restart_required, and that GetStatus's config_stale mirrors that until
// RestartVehicles actually applies the new config.
func TestConfigureRunningVehicleSetsRestartRequired(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()
	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)
	port := freePort(t)

	first := configureOne(t, inst, configWithArgs(inst, port, name, driver, "--a"))
	if !first.GetOk() {
		t.Fatalf("Configure (first call): %v", first)
	}

	if v := vehicleStatus(t, getStatus(t, inst), name); !v.GetRunning() || v.GetConfigStale() {
		t.Fatalf("expected %s running and not stale right after Configure, got %v", name, v)
	}

	// Reconfigure it again while it's still running.
	second := configureOne(t, inst, configWithArgs(inst, port, name, driver, "--b"))
	if !second.GetOk() {
		t.Fatalf("Configure (second call, vehicle running): %v", second)
	}
	if !second.GetReconfigured() {
		t.Error("expected VehicleResult.reconfigured=true")
	}
	if !second.GetRestartRequired() {
		t.Error("expected VehicleResult.restart_required=true when reconfiguring a running vehicle")
	}

	v := vehicleStatus(t, getStatus(t, inst), name)
	if !v.GetRunning() {
		t.Fatalf("expected %s to still be running (left alone), got %v", name, v)
	}
	if !v.GetConfigStale() {
		t.Error("expected VehicleStatus.config_stale=true after reconfiguring a running vehicle without restarting it")
	}

	// Restarting should pick up the new config and clear the stale flag.
	restartResp, err := inst.Client.RestartVehicles(ctx, eagledpb.RestartVehiclesRequest_builder{Names: []string{name}}.Build())
	if err != nil || len(restartResp.GetVehicles()) != 1 || !restartResp.GetVehicles()[0].GetOk() {
		t.Fatalf("RestartVehicles: resp=%v err=%v", restartResp, err)
	}

	v = vehicleStatus(t, getStatus(t, inst), name)
	if !v.GetRunning() {
		t.Fatalf("expected %s running after RestartVehicles, got %v", name, v)
	}
	if v.GetConfigStale() {
		t.Error("expected VehicleStatus.config_stale=false after RestartVehicles picked up the new config")
	}
}
