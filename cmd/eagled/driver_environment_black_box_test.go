package main_test

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// driverEnvWait bounds how long a test waits for the mock driver to record
// its environment.
const driverEnvWait = 10 * time.Second

// gabrielFlowConfig is a [gabriel] table whose flow takes each vehicle's
// telemetry, not its raw frames.
const gabrielFlowConfig = `
[[gabriel.flow.producers]]
name = "{vehicle}.telemetry"

[[gabriel.flow.engines]]
name = "{vehicle}.sink"
location = "local"

[[gabriel.flow.edges]]
from = "{vehicle}.telemetry"
to = "{vehicle}.sink"
timeout = "1s"
`

// TestDriverEnv checks the variables a driver is started with: where to
// publish its raw frames whenever vehicles run a Gabriel flow, even one that
// does not take them, and nothing otherwise. Its names are short, as they go
// into the paths of Unix sockets, which are at most 108 bytes.
func TestDriverEnv(t *testing.T) {
	const driver = "mockdriver"
	tests := []struct {
		name    string
		gabriel string
		want    string
	}{
		{"flow", gabrielFlowConfig, "GABRIEL_RAW_FRAMES_PRODUCER={vehicle}.raw_frames\nGABRIEL_FLOW={vehicle}\n"},
		{"noflow", "", "GABRIEL_RAW_FRAMES_PRODUCER=\nGABRIEL_FLOW=\n"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			inst := startEagled(t, "")
			writeMockDriver(t, inst.DataDir, driver)
			vehicleName := fmt.Sprintf("h%d", os.Getpid())

			result := configureOne(t, inst, fmt.Sprintf(`
port-base = %d
plugin-dir = %q
hostname = "test-daemon"

[backend.swarm-controller]
address = "127.0.0.1:1"

[[vehicles]]
name = %q
[vehicles.driver]
name = %q
%s`, freePort(t), inst.PluginDir, vehicleName, driver, test.gabriel))
			if !result.GetOk() {
				t.Fatalf("Configure: expected the vehicle to start, got error: %s", result.GetError())
			}

			envFile := filepath.Join(inst.DataDir, "steeleagle", "plugins", "driver", driver, "gabriel.env")
			deadline := time.Now().Add(driverEnvWait)
			for {
				env, err := os.ReadFile(envFile)
				if err == nil {
					if want := strings.ReplaceAll(test.want, "{vehicle}", vehicleName); string(env) != want {
						t.Fatalf("driver environment = %q, want %q", env, want)
					}
					return
				}
				if time.Now().After(deadline) {
					t.Fatalf("the driver recorded no environment: %v", err)
				}
				time.Sleep(100 * time.Millisecond)
			}
		})
	}
}
