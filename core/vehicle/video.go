package vehicle

import (
	"context"
	"fmt"
	"io"
	"os/exec"

	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	driverpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// streamRTSPVideo is a helper method that starts RTSP video streaming from the
// driver.
func (v *Vehicle) streamRTSPVideo(ctx context.Context) error {

	v.log.Info().Msg("starting RTSP video stream")

	client := driverpb.NewStreamServiceClient(v.driver)
	req := &driverpb.GetVideoStreamURLRequest{
		Resolution: driverpb.GetVideoStreamURLRequest_Resolution(v.videoCfg.Resolution),
	}

	// Send request to driver to get video stream URL
	resp, err := client.GetVideoStreamURL(ctx, req)
	if err != nil {
		return err
	}
	cmd := exec.CommandContext(
		ctx, "ffmpeg", getFFmpegArgs(resp.StreamUrl, v.videoCfg)...)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("error: %w", err)
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
		return fmt.Errorf("error starting FFmpeg: %w", err)
	}

	frameCh := make(chan []byte, 1)
	height, width := v.videoCfg.Resolution.Ints()
	go v.readFrames(ctx, stdout, frameCh, height*width*3, errCh)
	go v.consumeFrames(ctx, frameCh)

	return nil
}

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
func (v *Vehicle) consumeFrames(ctx context.Context, frameCh chan []byte) {
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
			f := &stream_msg_pb.EncodedFrame{
				Timestamp:   timestamppb.Now(),
				EncodedData: frame,
			}
			v.store.addFrame(f)
			if count%30 == 0 {
				v.log.Debug().Msgf("processed frame %d (%d bytes)\n", count, len(frame))
			}
		}
	}
}
