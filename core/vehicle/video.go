package vehicle

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os/exec"
	"strings"

	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"golang.org/x/sync/errgroup"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// stderrTailLines is the number of trailing FFmpeg stderr lines kept in
// memory.
const stderrTailLines = 20

// streamEncodedVideoFrames is a helper method that streams discrete encoded
// frames from the driver.
func (v *Vehicle) streamEncodedVideoFrames(ctx context.Context) error {
	v.log.Info().Msg("starting streaming encoded video frames")

	client := driverpb.NewStreamServiceClient(v.driver)
	builder := driverpb.StreamVideoFramesRequest_builder{}
	if fps := v.videoCfg.Fps; fps != 0 {
		builder.TargetFps = &fps
	}
	req := builder.Build()

	v.log.Info().Msg("sending StreamVideoFrames request to driver")
	stream, err := client.StreamVideoFrames(ctx, req)
	v.log.Info().Msg("StreamVideoFrames reply received")
	if err != nil {
		return err
	}
	for {
		if ctx.Err() != nil {
			return nil
		}
		f, err := stream.Recv()
		if err != nil {
			return err
		}
		if f.GetFrame() == nil {
			v.log.Debug().Msgf("got nil frame from driver")
		}
		v.store.addFrame(f.GetFrame())
	}
}

// streamRTSPVideo is a helper method that starts RTSP video streaming from the
// driver.
func (v *Vehicle) streamRTSPVideo(ctx context.Context) error {
	v.log.Info().Msg("starting RTSP video stream")

	client := driverpb.NewStreamServiceClient(v.driver)
	req := driverpb.GetVideoStreamURLRequest_builder{
		Resolution: driverpb.GetVideoStreamURLRequest_Resolution(v.videoCfg.Resolution),
	}.Build()

	// Send request to driver to get video stream URL
	resp, err := client.GetVideoStreamURL(ctx, req)
	if err != nil {
		return err
	}
	cmd := exec.CommandContext(
		ctx, "ffmpeg", getFFmpegArgs(resp.GetStreamUrl(), v.videoCfg)...)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("stderr pipe: %w", err)
	}
	// Keep only the last stderrTailLines lines of stderr in memory
	var tail []string
	stderrDone := make(chan struct{})
	go func() {
		defer close(stderrDone)
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			tail = append(tail, scanner.Text())
			if len(tail) > stderrTailLines {
				tail = tail[1:]
			}
		}
	}()

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("error starting FFmpeg: %w", err)
	}
	v.log.Info().Msg("FFmpeg streaming started")

	group, ctx := errgroup.WithContext(ctx)

	// readFrames must fully drain stdout, and the stderr scanner must fully
	// drain stderr, before cmd.Wait is called since exec.Cmd requires all
	// pipes to be read to completion first
	readersDone := make(chan struct{})
	frameCh := make(chan []byte, 1)
	height, width := v.videoCfg.Resolution.Ints()
	group.Go(func() error {
		defer close(readersDone)
		return v.readFrames(ctx, stdout, frameCh, height*width*3)
	})
	group.Go(func() error {
		return v.consumeFrames(ctx, frameCh)
	})
	group.Go(func() error {
		<-readersDone
		<-stderrDone
		waitErr := cmd.Wait()
		v.log.Error().Msgf("FFmpeg command exited:\n%s", strings.Join(tail, "\n"))
		return fmt.Errorf("FFmpeg exit status: %w", waitErr)
	})
	return group.Wait()
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
	filters := fmt.Sprintf("scale=%d:%d", width, height)
	if cfg.Fps != 0 {
		// Throttle to the desired frame rate by dropping/duplicating frames
		// upstream of the scaler, before they're written to the pipe.
		filters = fmt.Sprintf("fps=%d,%s", cfg.Fps, filters)
	}
	args = append(args,
		"-i", url,
		"-an", // drop audio
		"-vf", filters,
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
	frameSize int) error {
	defer close(out)
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		frame := make([]byte, frameSize)
		if _, err := io.ReadFull(r, frame); err != nil {
			v.log.Err(err).Msg("error reading frame")
			if err != io.EOF {
				return fmt.Errorf("frame read error: %w", err)
			}
			return err
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
func (v *Vehicle) consumeFrames(ctx context.Context, frameCh chan []byte) error {
	count := 1
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case frame, ok := <-frameCh:
			if !ok {
				return fmt.Errorf("frame channel closed")
			}
			count++
			f := telemetrypb.EncodedFrame_builder{
				Id:          uint64(count),
				Timestamp:   timestamppb.Now(),
				EncodedData: frame,
			}.Build()
			v.store.addFrame(f)
			if count%30 == 0 {
				v.log.Debug().Msgf("processed frame %d (%d bytes)\n", count, len(frame))
			}
		}
	}
}
