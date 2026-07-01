package vehicle

import (
	"context"
	"fmt"
	"io"
	"os/exec"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"google.golang.org/grpc"
)

type VideoStreamConfig struct {
	Codec      string
	BufCap     int
	Resolution driver_pb.GetVideoStreamURLRequest_Resolution
}

func resolutionDimensions(res driver_pb.GetVideoStreamURLRequest_Resolution) (int, int) {
	switch res {
	case driver_pb.GetVideoStreamURLRequest_RESOLUTION_480P:
		return 854, 480
	case driver_pb.GetVideoStreamURLRequest_RESOLUTION_720P:
		return 1280, 720
	case driver_pb.GetVideoStreamURLRequest_RESOLUTION_1080P:
		return 1920, 1080
	case driver_pb.GetVideoStreamURLRequest_RESOLUTION_4K:
		return 3840, 2160
	default:
		return 1280, 720
	}
}

type VideoStreamingType int

const (
	RTSP VideoStreamingType = iota
	Frames
)

func buildFFmpegCmd(rtspURL string, cfg VideoStreamConfig) []string {
	width, height := resolutionDimensions(cfg.Resolution)
	args := []string{
		//"-fflags", "nobuffer", // don't buffer before starting stream
		"-flags", "low_delay", // optimize latency
	}
	if cfg.Codec != "" {
		args = append(args, "-c:v", cfg.Codec) // hardware decoding
	}
	args = append(args,
		"-i", rtspURL,
		"-an", // drop audio
		"-vf", fmt.Sprintf("scale=%d:%d", width, height),
		"-pix_fmt", "bgr24", // convert to BGR 3 bytes per pixel
		"-f", "rawvideo", // no video container
		"-fps_mode", "passthrough", // don't retime/duplicate/drop frames
		"pipe:1", // write to fd 1
	)
	return args
}

// Read video frames from the reader and send them to a channel.
func (v *Vehicle) readFrames(
	r io.Reader,
	out chan []byte,
	frameSize int,
	errCh chan error) {
	defer close(out)
	for {
		frame := make([]byte, frameSize)
		if _, err := io.ReadFull(r, frame); err != nil {
			v.log.Err(err).Msg("error reading frame")
			if err != io.EOF {
				errCh <- fmt.Errorf("frame read error: %w", err)
				return
			}
			return
		}
		select {
		case out <- frame:
		default:
			// channel full, drop the previous unread frame and keep latest
			select {
			case <-out:
			default:
			}
			out <- frame
		}
	}
}

// Consume video frames from the given channel
func (v *Vehicle) consumeFrames(
	ctx context.Context,
	frameCh chan []byte,
	handler func([]byte),
	errCh chan error) {
	count := 0
	for {
		select {
		case <-ctx.Done():
			return
		case frame, ok := <-frameCh:
			if !ok {
				v.log.Error().Msg("frame channel closed")
				return
			}
			count++
			if handler != nil {
				handler(frame)
			}
			if count%30 == 0 {
				v.log.Debug().Msgf("processed frame %d (%d bytes)\n", count, len(frame))
			}
		}
	}
}

func (v *Vehicle) StartRTSPVideoStream(
	ctx context.Context,
	cfg VideoStreamConfig,
	handler func([]byte)) (chan error, error) {

	v.log.Info().Msg("starting RTSP video stream")

	client := driver_pb.NewStreamServiceClient(v.driver)
	req := &driver_pb.GetVideoStreamURLRequest{Resolution: cfg.Resolution}

	// Send request to driver to get video stream URL
	resp, err := client.GetVideoStreamURL(ctx, req)
	if err != nil {
		return nil, err
	}
	cmd := exec.CommandContext(ctx, "ffmpeg", buildFFmpegCmd(resp.StreamUrl, cfg)...)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("error: %w", err)
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, fmt.Errorf("error: %w", err)
	}
	errCh := make(chan error, 1)

	go func() {
		errOut, _ := io.ReadAll(stderr)
		err = cmd.Wait()
		v.log.Error().Msg("FFmpeg command exited")
		v.log.Error().Bytes("stderr", errOut).Msg("ffmpeg stderr")
		if err != nil {
			v.log.Err(err).Msg("FFmpeg non-zero exit status")
			errCh <- fmt.Errorf("ffmpeg non-zero exit status: %v", err)
			v.log.Error().Bytes("stderr", errOut).Msg("ffmpeg stderr")
			return
		}
	}()

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("error starting FFmpeg: %w", err)
	}
	v.log.Info().Msg("FFmpeg streaming started")

	frameCh := make(chan []byte, 1)
	height, width := resolutionDimensions(cfg.Resolution)
	go v.readFrames(stdout, frameCh, height*width*3, errCh)
	go v.consumeFrames(ctx, frameCh, handler, errCh)

	return errCh, nil
}

// Start video streaming with the given resolution
func (v *Vehicle) StartVideoStream(
	ctx context.Context,
	res driver_pb.GetVideoStreamURLRequest_Resolution,
	streamType VideoStreamingType,
	cfg VideoStreamConfig,
	handler func([]byte)) (chan error, error) {

	if streamType != RTSP {
		return nil, fmt.Errorf("only RTSP streaming is supported for now")
	}

	return v.StartRTSPVideoStream(ctx, cfg, handler)
}

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
