package sdk

import (
	"context"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// fakeDataClient is a minimal vehiclepb.DataServiceClient test double.
// Embedding the nil interface satisfies every method poll.go doesn't
// exercise (calling one would panic loudly, which is the point); only
// GetTelemetry is actually implemented.
type fakeDataClient struct {
	vehiclepb.DataServiceClient
	respond func() (*vehiclepb.GetTelemetryResponse, error)
}

func (f *fakeDataClient) GetTelemetry(ctx context.Context, in *vehiclepb.GetTelemetryRequest, opts ...grpc.CallOption) (*vehiclepb.GetTelemetryResponse, error) {
	return f.respond()
}

// constantTelemetry always returns the same telemetry snapshot.
func constantTelemetry(tel *telemetrypb.Telemetry) func() (*vehiclepb.GetTelemetryResponse, error) {
	resp := vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build()
	return func() (*vehiclepb.GetTelemetryResponse, error) { return resp, nil }
}

// failingTelemetry always fails the RPC.
func failingTelemetry() (*vehiclepb.GetTelemetryResponse, error) {
	return nil, status.Error(codes.Unavailable, "unavailable")
}

// testVehicleContext provides a mock vehicle context for testing.
func testVehicleContext(ctx context.Context, respond func() (*vehiclepb.GetTelemetryResponse, error)) *vehicleContext {
	return &vehicleContext{ctx: ctx, data: &fakeDataClient{respond: respond}}
}

// telemetryForGuidance provides mock telemetry to test guidance pollers.
func telemetryForGuidance(setpointAny *commonpb.GlobalPosition, actual *commonpb.GlobalPosition, status telemetrypb.MotionStatus) *telemetrypb.Telemetry {
	pi := telemetrypb.PositionInfo_builder{
		GlobalPosition: actual,
		Setpoint:       mustAnyNoT(setpointAny),
	}.Build()
	return telemetrypb.Telemetry_builder{
		MotionStatus: motionStatusP(status),
		PositionInfo: pi,
	}.Build()
}

// telemetryForGimbal provides mock telemetry to test gimbal pollers.
func telemetryForGimbal(setpointAny *commonpb.Pose, actual *commonpb.Pose) *telemetrypb.Telemetry {
	gi := telemetrypb.GimbalInfo_builder{
		PoseNeu:        actual,
		GimbalSetpoint: mustAnyNoT(setpointAny),
	}.Build()
	return telemetrypb.Telemetry_builder{GimbalInfo: gi}.Build()
}
