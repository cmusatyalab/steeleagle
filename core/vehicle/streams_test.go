package vehicle

import (
	"context"
	"testing"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc/codes"
	"google.golang.org/protobuf/proto"
)

// flowOf is a flow fed by producers, each to testEngine.
func flowOf(producers ...string) *config.FlowConfig {
	flow := &config.FlowConfig{Engines: []config.Engine{{Name: testEngine, Location: config.LocationLocal}}}
	for _, p := range producers {
		flow.Producers = append(flow.Producers, config.Producer{Name: p})
		flow.Edges = append(flow.Edges, config.Edge{From: p, To: testEngine, Timeout: "1s"})
	}
	return flow
}

// cameraOf is the request for the vehicle's camera name.
func cameraOf(v *Vehicle, name string) *driverpb.CameraRequest {
	return driverpb.CameraRequest_builder{Id: name, Uri: v.Name + "." + name}.Build()
}

// TestCameraRequest checks that a flow's cameras are streamed, with its
// primary camera as the primary, and that telemetry is not a camera.
func TestCameraRequest(t *testing.T) {
	v, _ := newTestVehicle(t)
	for _, tc := range []struct {
		name      string
		producers []string
		want      *driverpb.StreamCamerasRequest
	}{
		{"none", nil, &driverpb.StreamCamerasRequest{}},
		{"telemetry", []string{TelemetryProducerName}, &driverpb.StreamCamerasRequest{}},
		{"primary", []string{"front"}, driverpb.StreamCamerasRequest_builder{
			Primary: cameraOf(v, "front"),
		}.Build()},
		{"secondary", []string{"down", TelemetryProducerName}, driverpb.StreamCamerasRequest_builder{
			Secondaries: []*driverpb.CameraRequest{cameraOf(v, "down")},
		}.Build()},
		{"both", []string{"down", "rear"}, driverpb.StreamCamerasRequest_builder{
			Primary:     cameraOf(v, "rear"),
			Secondaries: []*driverpb.CameraRequest{cameraOf(v, "down")},
		}.Build()},
	} {
		got, err := v.cameraRequest(flowOf(tc.producers...))
		if err != nil {
			t.Errorf("%s: %v", tc.name, err)
		} else if !proto.Equal(got, tc.want) {
			t.Errorf("%s: got %v, want %v", tc.name, got, tc.want)
		}
	}
}

// TestCameraRequestInvalid checks that a flow can't have unknown producers or
// two primary cameras.
func TestCameraRequestInvalid(t *testing.T) {
	v, _ := newTestVehicle(t)
	_, err := v.cameraRequest(flowOf("front", "side"))
	expectCode(t, err, codes.InvalidArgument, "side")
	_, err = v.cameraRequest(flowOf("front", "down", "rear"))
	expectCode(t, err, codes.InvalidArgument, "front", "rear")
}

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
