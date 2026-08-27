package main_test

import (
	"fmt"
	"testing"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// configureOne pushes configToml to inst and returns the sole per-vehicle
// result, failing the test if Configure itself errors or doesn't return
// exactly one result.
func configureOne(t *testing.T, inst *eagledInstance, configToml string) *eagledpb.VehicleResult {
	t.Helper()
	resp, err := inst.Client.Configure(t.Context(), eagledpb.ConfigureRequest_builder{
		ConfigToml: configToml,
	}.Build())
	if err != nil {
		t.Fatalf("Configure: %v", err)
	}
	if len(resp.GetVehicles()) != 1 {
		t.Fatalf("Configure: expected 1 result, got %v", resp.GetVehicles())
	}
	return resp.GetVehicles()[0]
}

// TestConfigureRejectsInvalidVideoStreamType exercises
// buildVideoStreamConfig's stream-type validation: Configure should still
// succeed at the RPC level, but report this vehicle as failed rather than
// starting it with a bogus stream type.
func TestConfigureRejectsInvalidVideoStreamType(t *testing.T) {
	inst := startEagled(t, "")
	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)

	cfg := baseConfig(inst, freePort(t), name, driver) + `
[vehicles.video]
stream-type = "bogus"
`
	result := configureOne(t, inst, cfg)
	if result.GetOk() {
		t.Fatal("expected Configure to report failure for an invalid video.stream-type")
	}
	t.Logf("got expected error: %s", result.GetError())
}

// TestConfigureRejectsInvalidVideoResolution mirrors
// TestConfigureRejectsInvalidVideoStreamType for the resolution field.
func TestConfigureRejectsInvalidVideoResolution(t *testing.T) {
	inst := startEagled(t, "")
	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)

	cfg := baseConfig(inst, freePort(t), name, driver) + `
[vehicles.video]
resolution = "bogus"
`
	result := configureOne(t, inst, cfg)
	if result.GetOk() {
		t.Fatal("expected Configure to report failure for an invalid video.resolution")
	}
	t.Logf("got expected error: %s", result.GetError())
}

// TestConfigureRejectsUninstalledMissionPlugin exercises
// installedPluginPath's not-installed error for a plugin category other than
// the driver (which every other test already exercises implicitly, since an
// uninstalled driver is exactly how a bad-driver vehicle fails).
func TestConfigureRejectsUninstalledMissionPlugin(t *testing.T) {
	inst := startEagled(t, "")
	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)

	cfg := baseConfig(inst, freePort(t), name, driver) + `
[vehicles.mission]
name = "nonexistent-mission"
`
	result := configureOne(t, inst, cfg)
	if result.GetOk() {
		t.Fatal("expected Configure to report failure for an uninstalled mission plugin")
	}
	t.Logf("got expected error: %s", result.GetError())
}

// TestConfigureRejectsEmptyVehicleName exercises decodeConfig's rejection of
// a nameless [[vehicles]] entry at the RPC level: this is a malformed
// request, not a single vehicle failing to start, so Configure itself should
// error rather than reporting a per-vehicle failure.
func TestConfigureRejectsEmptyVehicleName(t *testing.T) {
	inst := startEagled(t, "")
	cfg := fmt.Sprintf(`
port-base = %d
hostname = "test-daemon"

[backend.swarm-controller]
address = "127.0.0.1:1"

[[vehicles]]
name = ""
`, freePort(t))

	_, err := inst.Client.Configure(t.Context(), eagledpb.ConfigureRequest_builder{ConfigToml: cfg}.Build())
	if err == nil {
		t.Fatal("expected Configure to reject a config with an empty vehicle name")
	}
	t.Logf("got expected error: %v", err)
}

// TestConfigureRejectsDuplicateVehicleName mirrors
// TestConfigureRejectsEmptyVehicleName for two [[vehicles]] entries sharing a
// name: without this check, the two entries would race on the same map key
// in startVehicles, and the second could be misreported as "already
// running" for a vehicle that never actually started.
func TestConfigureRejectsDuplicateVehicleName(t *testing.T) {
	inst := startEagled(t, "")
	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)

	cfg := fmt.Sprintf(`
port-base = %d
plugin-dir = %q
hostname = "test-daemon"

[backend.swarm-controller]
address = "127.0.0.1:1"

[[vehicles]]
name = %q
[vehicles.driver]
name = %q

[[vehicles]]
name = %q
[vehicles.driver]
name = %q
`, freePort(t), inst.PluginDir, name, driver, name, driver)

	_, err := inst.Client.Configure(t.Context(), eagledpb.ConfigureRequest_builder{ConfigToml: cfg}.Build())
	if err == nil {
		t.Fatal("expected Configure to reject a config listing the same vehicle name twice")
	}
	t.Logf("got expected error: %v", err)
}

// simulatedVehicleConfig is baseConfig's Simulate counterpart: no plugin-dir
// override (so both eagled and the aviary subprocess it spawns resolve the
// same XDG_RUNTIME_DIR-based default, matching steeleagle-aviary's actual
// socket convention -- see vehicle.go's aviarySocketPath), and an [aviary]
// table pointing at mockaviary instead of the real "uv run steeleagle-aviary".
func simulatedVehicleConfig(vehiclePort int, vehicleName string) string {
	return fmt.Sprintf(`
port-base = %d
hostname = "test-daemon"

[backend.swarm-controller]
address = "127.0.0.1:1"

[aviary]
command = [%q]

[[vehicles]]
name = %q
simulate = true
`, vehiclePort, mockAviaryBinary, vehicleName)
}

// TestConfigureSimulatedVehicle exercises the Simulate branch of
// newDriverPlugin: instead of installing/launching a driver plugin, the
// vehicle should attach to the shared aviary simulator's per-vehicle socket.
func TestConfigureSimulatedVehicle(t *testing.T) {
	inst := startEagled(t, "")
	const name = "harpy"

	result := configureOne(t, inst, simulatedVehicleConfig(freePort(t), name))
	if !result.GetOk() {
		t.Fatalf("Configure: expected simulated vehicle to start, got error: %s", result.GetError())
	}

	status, err := inst.Client.GetStatus(t.Context(), eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if v := vehicleStatus(t, status, name); !v.GetRunning() {
		t.Fatalf("expected simulated vehicle %s to be running, got %v", name, v)
	}
}

// TestConfigureMultipleVehiclesPartialFailure verifies that a Configure call
// with several vehicles reports per-vehicle results independently: one
// vehicle failing to start (here, an uninstalled driver) doesn't stop the
// others from starting, and doesn't abort the RPC.
func TestConfigureMultipleVehiclesPartialFailure(t *testing.T) {
	inst := startEagled(t, "")
	const goodName, driver = "harpy", "mockdriver"
	const badName = "griffin"
	writeMockDriver(t, inst.DataDir, driver)

	cfg := fmt.Sprintf(`
port-base = %d
plugin-dir = %q
hostname = "test-daemon"

[backend.swarm-controller]
address = "127.0.0.1:1"

[[vehicles]]
name = %q
[vehicles.driver]
name = %q

[[vehicles]]
name = %q
[vehicles.driver]
name = "does-not-exist"
`, freePort(t), inst.PluginDir, goodName, driver, badName)

	resp, err := inst.Client.Configure(t.Context(), eagledpb.ConfigureRequest_builder{
		ConfigToml: cfg,
	}.Build())
	if err != nil {
		t.Fatalf("Configure: %v", err)
	}
	if len(resp.GetVehicles()) != 2 {
		t.Fatalf("Configure: expected 2 results, got %v", resp.GetVehicles())
	}

	results := make(map[string]*eagledpb.VehicleResult)
	for _, r := range resp.GetVehicles() {
		results[r.GetName()] = r
	}
	if !results[goodName].GetOk() {
		t.Errorf("expected %s to start successfully, got error: %s", goodName, results[goodName].GetError())
	}
	if results[badName].GetOk() {
		t.Errorf("expected %s to fail to start (uninstalled driver), but it succeeded", badName)
	}

	status, err := inst.Client.GetStatus(t.Context(), eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if v := vehicleStatus(t, status, goodName); !v.GetRunning() {
		t.Fatalf("expected %s to be running, got %v", goodName, v)
	}
	for _, v := range status.GetVehicles() {
		if v.GetName() == badName {
			t.Fatalf("expected %s to be entirely absent from GetStatus (never successfully started), got %v", badName, v)
		}
	}
}
