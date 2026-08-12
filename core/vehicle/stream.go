package vehicle

import (
	"context"
	"io"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
)

// Stream telemetry from the driver, updating the vehicle data store.
func (v *Vehicle) streamTelemetry(ctx context.Context) error {
	client := driverpb.NewStreamServiceClient(v.driver)
	builder := driverpb.StreamTelemetryRequest_builder{}
	if fps := v.telemetryFps; fps != 0 {
		builder.TargetFps = &fps
	}
	req := builder.Build()
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
		v.store.addTelemetry(tel.GetTelemetry())
	}
}

// Stream video from the driver, updating the vehicle data store. This method
// chooses the stream type based on the vehicle's video configuration.
func (v *Vehicle) streamVideo(ctx context.Context) error {
	switch v.videoCfg.StreamType {
	case RTSP:
		return v.streamRTSPVideo(ctx)
	case Frames:
		return v.streamEncodedVideoFrames(ctx)
	}
	return nil
}

// retryAfterDelay waits streamRetryDelay before the caller retries a broken
// stream, returning early (false) if ctx is canceled first.
func retryAfterDelay(ctx context.Context) bool {
	select {
	case <-ctx.Done():
		return false
	case <-time.After(streamRetryDelay):
		return true
	}
}

// Start streaming video frames and telemetry from the driver, updating the
// vehicle data store.
func (v *Vehicle) startDriverStreaming(ctx context.Context) {
	go func() {
		for {
			err := v.streamTelemetry(ctx)
			if ctx.Err() != nil {
				return
			}
			v.log.Err(err).Msg("error streaming telemetry, restarting stream")
			if !retryAfterDelay(ctx) {
				return
			}
		}
	}()
	go func() {
		for {
			err := v.streamVideo(ctx)
			if ctx.Err() != nil {
				return
			}
			v.log.Err(err).Msg("error streaming frames, restarting stream")
			if !retryAfterDelay(ctx) {
				return
			}
		}
	}()
}
