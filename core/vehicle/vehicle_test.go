package vehicle_test

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	missionpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/mission"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func TestStartStop(t *testing.T) {
	driverPlugin, missionPlugin, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}

	pluginConfig := vehicle.PluginConfig{Driver: driverPlugin, Mission: missionPlugin}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	vehicle, err := vehicle.NewVehicle(pluginConfig, vehicle.WithLogger(logger))
	if err != nil {
		t.Fatalf("couldn't create vehicle")
	}
	ctx, cancel := context.WithCancel(t.Context())
	err = vehicle.Start(ctx)
	if err != nil {
		t.Fatalf("couldn't start vehicle")
	}

	// cancel vehicle context
	cancel()

	err = vehicle.Wait()
	if err != context.Canceled {
		t.FailNow()
	}
}

func TestPolicy(t *testing.T) {
	driverPlugin, missionPlugin, mClient, commCh, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}
	defer mClient.Close()

	serverSockDir := t.TempDir()
	serverLnAddr := filepath.Join(serverSockDir, ServerSocket)
	serverLn, err := net.Listen("unix", serverLnAddr)
	if err != nil {
		t.Fatalf("couldn't listen on server socket")
	}
	defer os.Remove(serverLnAddr)
	sClient, err := grpc.NewClient(
		fmt.Sprintf("unix://%s", serverLnAddr),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("couldn't create server client")
	}
	defer sClient.Close()

	pluginConfig := vehicle.PluginConfig{Driver: driverPlugin, Mission: missionPlugin}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	vehicle, err := vehicle.NewVehicle(pluginConfig, vehicle.WithServerListener(serverLn, nil), vehicle.WithLogger(logger))
	if err != nil {
		t.Fatalf("couldn't create vehicle")
	}
	err = vehicle.Start(t.Context())
	if err != nil {
		t.Fatalf("couldn't start vehicle")
	}

	missionControlClient := driverpb.NewControlServiceClient(mClient)
	serverControlClient := driverpb.NewControlServiceClient(sClient)
	serverMissionClient := missionpb.NewMissionServiceClient(sClient)

	// Server TakeOff call (REMOTE laws)
	ctx, _ := context.WithTimeout(t.Context(), time.Second)
	_, err = serverControlClient.TakeOff(ctx, &driverpb.TakeOffRequest{})
	if err != nil {
		t.Errorf("got error with server TakeOff rpc: %v", err)
	}
	select {
	case res := <-commCh:
		if res != "ControlService.TakeOff" {
			t.Errorf("incorrect command routing for TakeOff, got: %s", res)
		}
	case <-ctx.Done():
		t.Errorf("timeout reached on TakeOff request")
	}

	// Local Land call which should NOT be allowed in REMOTE laws
	ctx, _ = context.WithTimeout(t.Context(), time.Second)
	_, err = missionControlClient.Land(ctx, &driverpb.LandRequest{})
	if err == nil {
		t.Errorf("expected error with server Land rpc, got none")
	}

	// Server StartMission call which should transit to LOCAL laws (mission
	// control requests should now be allowed)
	ctx, _ = context.WithTimeout(t.Context(), time.Second)
	_, err = serverMissionClient.StartMission(ctx, &missionpb.StartMissionRequest{})
	if err != nil {
		t.Errorf("got error with server StartMission rpc: %v", err)
	}
	select {
	case res := <-commCh:
		if res != "MissionService.StartMission" {
			t.Errorf("incorrect command routing for StartMission, got: %s", res)
		}
	case <-ctx.Done():
		t.Errorf("timeout reached on StartMission request")
	}

	// Local Land call which should be allowed
	ctx, _ = context.WithTimeout(t.Context(), time.Second)
	_, err = missionControlClient.Land(ctx, &driverpb.LandRequest{})
	if err != nil {
		t.Errorf("got error with mission Land rpc: %v", err)
	}
	select {
	case res := <-commCh:
		if res != "ControlService.Land" {
			t.Errorf("incorrect command routing for Land, got: %s", res)
		}
	case <-ctx.Done():
		t.Errorf("timeout reached on Land request")
	}

	// Server TakeOff call should reset to REMOTE laws
	ctx, _ = context.WithTimeout(t.Context(), time.Second)
	_, err = serverControlClient.TakeOff(ctx, &driverpb.TakeOffRequest{})
	if err != nil {
		t.Errorf("got error with server TakeOff rpc: %v", err)
	}
	select {
	case res := <-commCh:
		if res != "ControlService.TakeOff" {
			t.Errorf("incorrect command routing for TakeOff, got: %s", res)
		}
	case <-ctx.Done():
		t.Errorf("timeout reached on TakeOff request")
	}

	// Local Land call which should NOT be allowed in REMOTE laws
	ctx, _ = context.WithTimeout(t.Context(), time.Second)
	_, err = missionControlClient.Land(ctx, &driverpb.LandRequest{})
	if err == nil {
		t.Errorf("expected error with server Land rpc, got none")
	}
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

// TODO:
// Error cases
// - nil driver plugin
// - reserved listener name
