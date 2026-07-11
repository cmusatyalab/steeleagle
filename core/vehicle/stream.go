package vehicle

import (
	"context"
	"io"

	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Stream telemetry from the driver, updating the vehicle store.
func (v *Vehicle) streamTelemetry(ctx context.Context) error {
	client := driver_pb.NewStreamServiceClient(v.driver)
	req := &driver_pb.StreamTelemetryRequest{}
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

// Start streaming video frames and telemetry from the driver, updating the
// vehicle data store.
func (v *Vehicle) startDriverStreaming(ctx context.Context) error {
	frameHandler := func(frameBytes []byte) {
		f := &stream_msg_pb.EncodedFrame{
			Timestamp:   timestamppb.Now(),
			EncodedData: frameBytes,
		}
		v.store.addFrame(f)
	}
	videoErrCh, err := v.startVideoStream(ctx, RTSP, v.videoCfg, frameHandler)
	if err != nil {
		return nil
	}

	go func() { v.errCh <- v.streamTelemetry(ctx) }()
	go func() { v.errCh <- <-videoErrCh }()

    return nil
}
