package vehicle_test

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// TestThirdPartyPlugin verifies that a plugin passed via PluginConfig.Plugins
// (i.e. one that is neither the driver nor the mission plugin) is launched and
// that its listener is registered and served by the vehicle's gRPC server, the
// same as the driver/mission plugins.
func TestVehicleThirdPartyPlugin(t *testing.T) {
	driverPlugin, missionPlugin, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}

	// Create a shim plugin representing an already-running third-party plugin.
	// It only needs a listen socket: the vehicle should pick up the returned
	// listener and serve it alongside the other listeners.
	lnSockPath := filepath.Join(t.TempDir(), "thirdparty.sock")
	acl := util.GetACL([]string{}, []int{os.Getpid()})
	thirdPartyPlugin, err := util.CreateShimPlugin(
		"",
		lnSockPath,
		util.WithAuthCode(util.ExternalCode),
		util.WithACL(acl),
	)
	if err != nil {
		t.Fatalf("couldn't create third-party plugin: %v", err)
	}

	pluginConfig := vehicle.PluginConfig{
		Driver:  driverPlugin,
		Mission: missionPlugin,
		Plugins: []util.Plugin{thirdPartyPlugin},
	}
	v, err := NewVehicle(t, pluginConfig)
	if err != nil {
		t.Fatalf("couldn't create vehicle")
	}
	err = v.Start(t.Context())
	if err != nil {
		t.Fatalf("couldn't start vehicle: %v", err)
	}

	// Dial the listener that the vehicle registered for the third-party
	// plugin. If the vehicle's launch loop correctly picked up and served this
	// listener, RPCs sent to it reach the vehicle's auth interceptor and
	// policy engine.
	conn, err := grpc.NewClient(
		fmt.Sprintf("unix://%s", lnSockPath),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("couldn't create third-party client: %v", err)
	}
	defer conn.Close()

	controlSvcClient := driverpb.NewControlServiceClient(conn)
	ctx, cancel := context.WithTimeout(t.Context(), time.Second)
	t.Cleanup(cancel)
	// Try to issue a take off request. External-tagged callers aren't
	// authorized by the default policy, so the request is expected to be
	// rejected.
	_, err = controlSvcClient.TakeOff(ctx, &driverpb.TakeOffRequest{})
	if status.Code(err) != codes.PermissionDenied {
		t.Errorf("expected PermissionDenied routing TakeOff through third-party plugin listener, got: %v", err)
	}
	dataSvcClient := vehiclepb.NewDataServiceClient(conn)
	ctx, cancel = context.WithTimeout(t.Context(), time.Second)
	t.Cleanup(cancel)
	// Try to fetch telemetry. External-tagged callers should be authorized to
	// get this data from the vehicle.
	_, err = dataSvcClient.GetTelemetry(ctx, &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Errorf("expected plugin to be able to get telemetry: %v", err)

	}
	streamSvcClient := driverpb.NewStreamServiceClient(conn)
	ctx, cancel = context.WithTimeout(t.Context(), time.Second)
	t.Cleanup(cancel)
	// Try to get the video stream URL. External-tagged callers should not be
	// authorized by the default policy, so the request is expected to be
	// rejected.
	_, err = streamSvcClient.GetVideoStreamURL(ctx, &driverpb.GetVideoStreamURLRequest{})
	if status.Code(err) != codes.PermissionDenied {
		t.Errorf("expected PermissionDenied routing GetVideoStreamURL through third-party plugin listener, got: %v", err)
	}
}
