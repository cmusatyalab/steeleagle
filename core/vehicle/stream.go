package vehicle

import (
	"context"
	"io"

	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	driverpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"github.com/rs/zerolog/log"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Stream telemetry from the driver, updating the vehicle store.
func (v *Vehicle) streamTelemetry(ctx context.Context) error {
	client := driverpb.NewStreamServiceClient(v.driver)
	req := &driverpb.StreamTelemetryRequest{}
	stream, err := client.StreamTelemetry(ctx, req)
	if err != nil {
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
			log.Err(err).Msg("error receiving telemetry from driver")
			continue
		}
		if tel == nil {
			log.Error().Msg("received nil telemetry from driver")
			continue
		}
		v.store.addTelemetry(tel.Telemetry)
	}
}

// Start streaming video frames and telemetry from the driver, updating the
// vehicle data store.
func (v *Vehicle) startDriverStreaming(ctx context.Context) (<-chan error, error) {
	frameHandler := func(frameBytes []byte) {
		f := &stream_msg_pb.EncodedFrame{
			Timestamp:   timestamppb.Now(),
			EncodedData: frameBytes,
		}
		v.store.addFrame(f)
	}
	videoErrCh, err := v.startVideoStream(ctx, RTSP, v.videoStreamConfig, frameHandler)
	if err != nil {
		return nil, err
	}

	errCh := make(chan error, 2)
	go func() { errCh <- v.streamTelemetry(ctx) }()
	go func() { errCh <- <-videoErrCh }()

	return errCh, nil
}
