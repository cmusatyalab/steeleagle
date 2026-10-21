package vehicle

import (
	"context"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// SetDataflow parses and executes a dataflow from TOML bytes.
func (v *Vehicle) SetDataflow(
	ctx context.Context,
	req *vehiclepb.SetDataflowRequest,
) (*vehiclepb.SetDataflowResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "SetDataflow not implemented")
}

// RevertToDefaultDataflow sets the current dataflow back to the default.
func (v *Vehicle) RevertToDefaultDataflow(
	ctx context.Context,
	req *vehiclepb.RevertToDefaultDataflowRequest,
) (*vehiclepb.RevertToDefaultDataflowResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "RevertToDefaultDataflow not implemented")
}

// GetResult queries a dataflow for results.
func (v *Vehicle) GetResult(
	ctx context.Context,
	req *vehiclepb.GetResultRequest,
) (*vehiclepb.GetResultResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "GetResult not implemented")
}

// GetTelemetry queries received telemetry.
func (v *Vehicle) GetTelemetry(
	ctx context.Context,
	req *vehiclepb.GetTelemetryRequest,
) (*vehiclepb.GetTelemetryResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "GetTelemetry not implemented")
}

// GetStreamInfo gets information about available streams.
func (v *Vehicle) GetStreamInfo(
	ctx context.Context,
	req *vehiclepb.GetStreamInfoRequest,
) (*vehiclepb.GetStreamInfoResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "GetStreamInfo not implemented")
}
