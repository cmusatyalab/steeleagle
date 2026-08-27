package vehicle_test

import (
	"context"
	"net"
	"sync/atomic"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"google.golang.org/grpc"
)

// crashablePlugin wraps a real util.Plugin so a test can simulate it crashing
// on demand. Wait blocks on exitErr instead of the wrapped plugin's own Wait,
// while Start still delegates to the real plugin and counts how many times
// it's run.
type crashablePlugin struct {
	util.Plugin
	starts  atomic.Int32
	exitErr chan error
}

func newCrashablePlugin(p util.Plugin) *crashablePlugin {
	return &crashablePlugin{Plugin: p, exitErr: make(chan error, 1)}
}

func (p *crashablePlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	p.starts.Add(1)
	return p.Plugin.Start(ctx)
}

func (p *crashablePlugin) Wait() error { return <-p.exitErr }

var _ util.Plugin = (*crashablePlugin)(nil)

// waitForStarts polls until p has been started want times, failing the test if
// it doesn't happen in time.
func waitForStarts(t *testing.T, p *crashablePlugin, want int32) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if p.starts.Load() >= want {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("plugin was not restarted in time: started %d time(s), wanted %d", p.starts.Load(), want)
}

// TestVehicleRestartsDriverPluginOnCrash verifies that when the driver
// plugin's process exits unexpectedly, the vehicle's plugin monitor starts it
// again.
func TestVehicleRestartsDriverPluginOnCrash(t *testing.T) {
	realDriver, _, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugins: %v", err)
	}
	driver := newCrashablePlugin(realDriver)

	v, err := NewVehicle(t, vehicle.PluginConfig{Driver: driver})
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}
	if err := v.Start(t.Context()); err != nil {
		t.Fatalf("couldn't start vehicle: %v", err)
	}
	waitForStarts(t, driver, 1)

	driver.exitErr <- context.DeadlineExceeded // simulate the driver process dying on its own
	waitForStarts(t, driver, 2)
}

// TestVehicleRestartsMissionPluginOnCrash is the same, for the mission plugin.
func TestVehicleRestartsMissionPluginOnCrash(t *testing.T) {
	realDriver, realMission, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugins: %v", err)
	}
	mission := newCrashablePlugin(realMission)

	v, err := NewVehicle(t, vehicle.PluginConfig{Driver: realDriver, Mission: mission})
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}
	if err := v.Start(t.Context()); err != nil {
		t.Fatalf("couldn't start vehicle: %v", err)
	}
	waitForStarts(t, mission, 1)

	mission.exitErr <- context.DeadlineExceeded
	waitForStarts(t, mission, 2)
}
