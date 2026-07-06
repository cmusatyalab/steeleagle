package vehicle_test

import (
	"context"
	"net"
	"testing"

	vehicle "github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog"
)

func TestProxy(t *testing.T) {
	initializeSocketFiles(t)
	// TODO: test socket proxying between driver and mission, and
	// ensure that the stream service is not visible
	commCh := make(chan string, 0)
	driverServer, missionServer, err := setupServers(t, commCh)
	if err != nil {
		t.Fatalf("couldn't start driver and mission servers: %v", err)
	}
	defer driverServer.GracefulStop()
	defer missionServer.GracefulStop()
	driverPlugin, missionPlugin, err := setupPlugins(t)
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}
	serverLn, err := net.Listen("unix", ServerSocket)
	if err != nil {
		t.Fatalf("couldn't listen on server socket")
	}

	pluginConfig := vehicle.PluginConfig{Driver: driverPlugin, Mission: missionPlugin}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testWriter{t}})
	vehicle, err := vehicle.NewVehicle(pluginConfig, vehicle.WithServerListener(serverLn), vehicle.WithLogger(logger))
	if err != nil {
		t.Fatalf("couldn't create vehicle")
	}
	err = vehicle.Start(context.Background())
	if err != nil {
		t.Fatalf("couldn't start vehicle")
	}
	vehicle.Stop()
}

func TestPolicy(t *testing.T) {
	// TODO: test permissions + state transitions with the basic law
	// and then with a custom law
}

func TestTelemetry(t *testing.T) {
	// TODO: test getting telemetry stream
}

func TestVideoFrames(t *testing.T) {
	// TODO: test getting video frame stream
}

func TestRTSPStream(t *testing.T) {
	// TODO: test redirecting RTSP stream/re-encoding
}

func TestPluginConfig(t *testing.T) {
	// TODO: start vehicle without a driver and then without a mission,
	// see how error states are handled
}

func TestDMSFailsafe(t *testing.T) {
	// TODO: dead man's switch failsafe
}

func TestServerFailsafe(t *testing.T) {
	// TODO: server dc failsafe
}

func TestMissionFailsafe(t *testing.T) {
	// TODO: server dc failsafe
}

func TestAbandonFailsafe(t *testing.T) {
	// TODO: server and mission dc failsafe
}
