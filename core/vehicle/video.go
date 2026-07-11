package vehicle

import (
	"context"
	"fmt"
	"io"
	"os/exec"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
)

// getFFmpegArgs returns the arguments for the FFmpeg command corresponding
// to the VideoStreamConfig.
func getFFmpegArgs(url string, cfg VideoStreamConfig) []string {
	// Build the args from the config
	width, height := cfg.Resolution.Ints()
	args := []string{
		"-flags", "low_delay", // optimize for low latency
	}

	// Add hardware decoding if it is requested
	if cfg.Codec != "" {
		args = append(args, "-c:v", cfg.Codec)
	}
	args = append(args,
		"-i", url,
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
	ctx context.Context,
	r io.Reader,
	out chan []byte,
	frameSize int,
	errCh chan error) {
	defer close(out)
	for {
		if err := ctx.Err(); err != nil {
			errCh <- err
			return
		}
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
	handler func([]byte)) {
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

func (v *Vehicle) startRTSPVideoStream(
	ctx context.Context,
	handler func([]byte)) (<-chan error, error) {

	v.log.Info().Msg("starting RTSP video stream")

	client := driver_pb.NewStreamServiceClient(v.driver)
	req := &driver_pb.GetVideoStreamURLRequest{
        Resolution: driver_pb.GetVideoStreamURLRequest_Resolution(v.videoCfg.Resolution),
    }

	// Send request to driver to get video stream URL
	resp, err := client.GetVideoStreamURL(ctx, req)
	if err != nil {
		return nil, err
	}
	cmd := exec.CommandContext(
		ctx, "ffmpeg", getFFmpegArgs(resp.StreamUrl, v.videoCfg)...)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("error: %w", err)
	}
	errCh := make(chan error, 1)

	v.log.Info().Msg("FFmpeg streaming started")
	go func() {
		err = cmd.Wait()
		v.log.Error().Msg("FFmpeg command exited")
		if err != nil {
			v.log.Err(err).Msg("FFmpeg non-zero exit status")
			errCh <- fmt.Errorf("FFmpeg non-zero exit status: %v", err)
			return
		}
	}()

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("error starting FFmpeg: %w", err)
	}

	frameCh := make(chan []byte, 1)
	height, width := v.videoCfg.Resolution.Ints()
	go v.readFrames(ctx, stdout, frameCh, height*width*3, errCh)
	go v.consumeFrames(ctx, frameCh, handler)

	return errCh, nil
}

// Start video streaming with the given resolution
func (v *Vehicle) startVideoStream(
	ctx context.Context,
	streamType VideoStreamingType,
	cfg VideoStreamConfig,
	handler func([]byte)) (<-chan error, error) {

	if streamType != RTSP {
		return nil, fmt.Errorf("only RTSP streaming is supported for now")
	}

	return v.startRTSPVideoStream(ctx, handler)
}
