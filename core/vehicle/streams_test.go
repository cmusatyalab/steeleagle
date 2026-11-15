package vehicle

import (
	"context"
	"testing"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc/codes"
)

// TestStreamTelemetry checks that a started vehicle asks the driver to
// publish telemetry on its telemetry producer.
func TestStreamTelemetry(t *testing.T) {
	v, driver := newTestVehicle(t)
	driver.mu.Lock()
	defer driver.mu.Unlock()
	if len(driver.telemetry) != 1 || driver.telemetry[0] != v.Name+"."+TelemetryProducerName {
		t.Errorf("telemetry streamed on %v, want %s.%s", driver.telemetry, v.Name, TelemetryProducerName)
	}
}

// TestStreamsUnsupported checks that a driver that doesn't stream is never
// asked to, and that only streaming no cameras succeeds.
func TestStreamsUnsupported(t *testing.T) {
	v, driver := testVehicle(t)
	v.config.Driver = &config.DriverCap{Cameras: testCameras}
	if _, _, err := v.Start(context.Background()); err != nil {
		t.Fatal(err)
	}
	if err := v.streamCameras(context.Background(), &driverpb.StreamCamerasRequest{}); err != nil {
		t.Errorf("streaming no cameras: %v", err)
	}
	req := driverpb.StreamCamerasRequest_builder{Primary: cameraOf(v, "front")}.Build()
	expectCode(t, v.streamCameras(context.Background(), req), codes.FailedPrecondition)
	driver.mu.Lock()
	defer driver.mu.Unlock()
	if len(driver.cameras) != 0 || len(driver.telemetry) != 0 {
		t.Error("driver was asked to stream")
	}
}
