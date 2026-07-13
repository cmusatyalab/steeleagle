package vehicle

import (
	"context"
	"io"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
)

// Stream telemetry from the driver, updating the vehicle data store.
func (v *Vehicle) streamTelemetry(ctx context.Context) error {
	client := driverpb.NewStreamServiceClient(v.driver)
	req := &driverpb.StreamTelemetryRequest{}
	stream, err := client.StreamTelemetry(ctx, req)
	if err != nil {
		v.log.Error().Err(err).Msg("couldn't get telemetry stream from driver")
		return err
	}
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		tel, err := stream.Recv()
		if err == io.EOF {
			return err
		}
		if err != nil {
			v.log.Error().Err(err).Msg("error receiving telemetry from driver")
			continue
		}
		if tel == nil {
			v.log.Error().Msg("received nil telemetry from driver")
			continue
		}
		v.store.addTelemetry(tel.Telemetry)
	}
}

// Stream video from the driver, updating the vehicle data store. This method
// chooses the stream type based on the vehicle's video configuration.
func (v *Vehicle) streamVideo(ctx context.Context) error {
	return v.streamRTSPVideo(ctx)
}

// Start streaming video frames and telemetry from the driver, updating the
// vehicle data store.
func (v *Vehicle) startDriverStreaming(ctx context.Context) {
	go func() { v.streamTelemetry(ctx) }()
	go func() { v.streamVideo(ctx) }()
}
