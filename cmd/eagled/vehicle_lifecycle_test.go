package main_test

import (
	"testing"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// vehicleStatus finds name in resp's vehicle list, failing the test if it's
// missing.
func vehicleStatus(t *testing.T, resp *eagledpb.GetStatusResponse, name string) *eagledpb.VehicleStatus {
	t.Helper()
	for _, v := range resp.GetVehicles() {
		if v.GetName() == name {
			return v
		}
	}
	t.Fatalf("vehicle %q not present in GetStatus response: %v", name, resp)
	return nil
}

// TestVehicleLifecycle exercises Configure -> StopVehicles -> RestartVehicles
// -> ForgetVehicles end to end through eagled's real DaemonService.
func TestVehicleLifecycle(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()

	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)

	cfgResp, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: baseConfig(inst, freePort(t), name, driver),
	}.Build())
	if err != nil {
		t.Fatalf("Configure: %v", err)
	}
	if len(cfgResp.GetVehicles()) != 1 || !cfgResp.GetVehicles()[0].GetOk() {
		t.Fatalf("Configure did not start %s: %v", name, cfgResp.GetVehicles())
	}

	status, err := inst.Client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if !status.GetConfigured() {
		t.Fatal("expected daemon to report configured")
	}
	if v := vehicleStatus(t, status, name); !v.GetRunning() {
		t.Fatalf("expected %s to be running after Configure, got %v", name, v)
	}

	// StopVehicles: should succeed, and the vehicle should still be known
	// (present in GetStatus, just not running) rather than disappearing.
	stopResp, err := inst.Client.StopVehicles(ctx, eagledpb.StopVehiclesRequest_builder{Names: []string{name}}.Build())
	if err != nil || len(stopResp.GetVehicles()) != 1 || !stopResp.GetVehicles()[0].GetOk() {
		t.Fatalf("StopVehicles: resp=%v err=%v", stopResp, err)
	}
	status, err = inst.Client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus after Stop: %v", err)
	}
	if v := vehicleStatus(t, status, name); v.GetRunning() {
		t.Fatalf("expected %s to not be running after StopVehicles, got %v", name, v)
	}

	// A second StopVehicles should fail: the vehicle isn't running.
	stopResp2, err := inst.Client.StopVehicles(ctx, eagledpb.StopVehiclesRequest_builder{Names: []string{name}}.Build())
	if err != nil {
		t.Fatalf("StopVehicles (second): %v", err)
	}
	if stopResp2.GetVehicles()[0].GetOk() {
		t.Error("expected second StopVehicles to fail, vehicle isn't running")
	}

	// RestartVehicles should bring it back, using the config StopVehicles
	// left in place.
	restartResp, err := inst.Client.RestartVehicles(ctx, eagledpb.RestartVehiclesRequest_builder{Names: []string{name}}.Build())
	if err != nil || len(restartResp.GetVehicles()) != 1 || !restartResp.GetVehicles()[0].GetOk() {
		t.Fatalf("RestartVehicles: resp=%v err=%v", restartResp, err)
	}
	status, err = inst.Client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus after Restart: %v", err)
	}
	if v := vehicleStatus(t, status, name); !v.GetRunning() {
		t.Fatalf("expected %s to be running again after RestartVehicles, got %v", name, v)
	}

	// ForgetVehicles: should succeed and remove the vehicle entirely.
	forgetResp, err := inst.Client.ForgetVehicles(ctx, eagledpb.ForgetVehiclesRequest_builder{Names: []string{name}}.Build())
	if err != nil || len(forgetResp.GetVehicles()) != 1 || !forgetResp.GetVehicles()[0].GetOk() {
		t.Fatalf("ForgetVehicles: resp=%v err=%v", forgetResp, err)
	}
	status, err = inst.Client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus after Forget: %v", err)
	}
	for _, v := range status.GetVehicles() {
		if v.GetName() == name {
			t.Fatalf("expected %s to be gone after ForgetVehicles, got %v", name, v)
		}
	}

	// RestartVehicles on a forgotten vehicle should fail: not configured.
	restartResp2, err := inst.Client.RestartVehicles(ctx, eagledpb.RestartVehiclesRequest_builder{Names: []string{name}}.Build())
	if err != nil {
		t.Fatalf("RestartVehicles (after Forget): %v", err)
	}
	if restartResp2.GetVehicles()[0].GetOk() {
		t.Error("expected RestartVehicles to fail after ForgetVehicles, vehicle isn't configured")
	}
}
