package vehicle

import (
	"context"
	"fmt"
	"io"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"google.golang.org/grpc"
)

// Start streaming telemetry from the vehicle driver. Launches a goroutine that
// performs the streaming and updates the data service as telemetry is
// received. The launched goroutine uses the returned error channel to report
// any errors. This method is non-blocking.
func (v *Vehicle) StartTelemetryStream(ctx context.Context) (chan error, error) {
	client := driver_pb.NewStreamServiceClient(v.driver)
	req := &driver_pb.StreamTelemetryRequest{}

	// Send request to driver
	stream, err := client.StreamTelemetry(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to start stream: %w", err)
	}

	errCh := make(chan error, 1)
	// Launch goroutine to stream telemetry
	go func() {
		for {
			// check if context has ended
			if err := ctx.Err(); err != nil {
				v.log.Err(err).Msg("telemetry stream ended")
				errCh <- err
				return
			}
			v.recvTelemetry(ctx, stream, errCh)
		}
	}()
	return errCh, nil
}

// Encapsulates telemetry stream response along with an error for sending
// in a channel
type TelemetryStreamResponse struct {
	resp *driver_pb.StreamTelemetryResponse
	err  error
}

// Receive telemetry from a telemetry stream, sending any errors to the
// specified error channel.
func (v *Vehicle) recvTelemetry(
	ctx context.Context,
	stream grpc.ServerStreamingClient[driver_pb.StreamTelemetryResponse],
	errCh chan error) {
	ch := make(chan TelemetryStreamResponse)
	// Invoke blocking call to receive stream data in another goroutine
	go func() {
		resp, err := stream.Recv()
		ch <- TelemetryStreamResponse{resp: resp, err: err}
	}()

	// Wait to receive stream data or context to end
	select {
	case <-ctx.Done():
		v.log.Err(ctx.Err()).Msg("telemetry stream ended")
		errCh <- ctx.Err()
		return
	case res := <-ch:
		if res.err == io.EOF {
			v.log.Err(res.err).Msg("telemetry stream ended")
			errCh <- res.err
			return
		}
		if res.err != nil {
			v.log.Err(res.err).Msg("telemetry stream error")
			errCh <- res.err
			return
		}
		//TODO: we don't want a circular reference here!
		//v.dataSvc.updateLatestTelemetry(res.resp.Telemetry)
	}
}
