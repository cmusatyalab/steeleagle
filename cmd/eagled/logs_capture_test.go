package main_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// waitForFileContains polls path until it contains substr.
func waitForFileContains(t *testing.T, path, substr string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	var last string
	for time.Now().Before(deadline) {
		if data, err := os.ReadFile(path); err == nil {
			last = string(data)
			if strings.Contains(last, substr) {
				return
			}
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("%s never contained %q; last contents:\n%s", path, substr, last)
}

func TestLogsCapturedPerSourceOnDisk(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()

	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)
	cfgResp, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: baseConfig(inst, freePort(t), name, driver),
	}.Build())
	if err != nil || len(cfgResp.GetVehicles()) != 1 || !cfgResp.GetVehicles()[0].GetOk() {
		t.Fatalf("Configure: %v, %v", cfgResp, err)
	}

	logDir := filepath.Join(inst.DataDir, "steeleagle", "logs")
	// eagled's own zerolog output, tagged with its source.
	waitForFileContains(t, filepath.Join(logDir, "daemon.log"), "Configure received")
	waitForFileContains(t, filepath.Join(logDir, "daemon.log"), `"source":"daemon"`)
	// the vehicle core's logger.
	waitForFileContains(t, filepath.Join(logDir, "harpy.log"), "vehicle started")
	// the driver plugin's process output.
	waitForFileContains(t, filepath.Join(logDir, "harpy-driver.log"), "mockdriver ready")

	// Forgetting a vehicle must leave its logs on disk.
	if _, err := inst.Client.ForgetVehicles(ctx, eagledpb.ForgetVehiclesRequest_builder{Names: []string{name}}.Build()); err != nil {
		t.Fatalf("ForgetVehicles: %v", err)
	}
	if _, err := os.Stat(filepath.Join(logDir, "harpy.log")); err != nil {
		t.Fatalf("harpy.log must survive ForgetVehicles: %v", err)
	}
}
