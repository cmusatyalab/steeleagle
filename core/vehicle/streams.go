package vehicle

import (
	"context"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// streamTelemetry asks the driver to publish telemetry, if it supports
// streaming it.
func (v *Vehicle) streamTelemetry(ctx context.Context) error {
	if !v.config.Driver.Supports(StreamTelemetryMethod) {
		v.log.Warn().Msg("driver does not stream telemetry")
		return nil
	}
	ctx, cancel := context.WithTimeout(ctx, StreamTimeout)
	defer cancel()
	req := driverpb.StreamTelemetryRequest_builder{Uri: v.streamInfo.telemetry}.Build()
	// The driver's server may not be ready right after it starts
	_, err := driverpb.NewStreamServiceClient(v.driverInfo.conn).StreamTelemetry(ctx, req, grpc.WaitForReady(true))
	return err
}

// streamCameras asks the driver to stream cameras, replacing those it
// streamed before. A driver that doesn't support streaming cameras is only
// asked for none.
func (v *Vehicle) streamCameras(ctx context.Context, req *driverpb.StreamCamerasRequest) error {
	if !v.config.Driver.Supports(StreamCamerasMethod) {
		if req.HasPrimary() || len(req.GetSecondaries()) > 0 {
			return status.Error(codes.FailedPrecondition, "driver does not stream cameras")
		}
		return nil
	}
	ctx, cancel := context.WithTimeout(ctx, StreamTimeout)
	defer cancel()
	_, err := driverpb.NewStreamServiceClient(v.driverInfo.conn).StreamCameras(ctx, req, grpc.WaitForReady(true))
	return err
}

// producerUri is the fully qualified name of the vehicle's producer name.
func (v *Vehicle) producerUri(name string) string {
	return v.Name + "." + name
}
