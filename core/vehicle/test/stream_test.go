package vehicle_test

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"testing"
	"time"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"
)

const (
	testWidth         = 320
	testHeight        = 240
	testFPS           = 10
	testDuration      = 3
	testVideoFilename = "test.mp4"
	minFrames         = testFPS * testDuration
	bufConnSize       = 1 << 20
)

func testStreaming(t *testing.T, inputFileURL string, timeout time.Duration) {
	driverConn, err := newMockDriverConn(t, inputFileURL)
	if err != nil {
		t.Fatalf("error creating mock driver connection: %v", err)
	}

	pluginCfg := vehicle.PluginConfig{}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testWriter{t}})
	v, err := vehicle.NewVehicle(
		pluginCfg,
		vehicle.WithDriverConn(driverConn),
		vehicle.WithLogger(logger))
	if err != nil {
		t.Fatalf("error creating vehicle: %v", err)
	}
	resolution := driver_pb.GetVideoStreamURLRequest_RESOLUTION_720P
	videoCfg := vehicle.VideoStreamConfig{Resolution: resolution}

	numFrames := 0
	handler := func(frame []byte) {
		numFrames += 1
	}

	errCh, err := v.StartRTSPVideoStream(t.Context(), videoCfg, handler)
	if err != nil {
		t.Fatalf("error starting video stream: %v", err)
	}

	time.Sleep(timeout)

	select {
	case err = <-errCh:
		t.Fatalf("video stream error: %v", err)
	default:
	}

	if numFrames < minFrames {
		t.Fatalf("only received %d frames", numFrames)
	}
}

func getFreePort(t *testing.T) int {
	l, err := net.ListenPacket("udp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("error finding free port: %v", err)
	}
	defer l.Close()
	return l.LocalAddr().(*net.UDPAddr).Port
}

func pushTestVideo(t *testing.T, videoPath string, port int, path string) {
	rtspURL := fmt.Sprintf("rtsp://127.0.0.1:%d/%s", port, path)
	cmd := exec.CommandContext(t.Context(), "ffmpeg",
		"-re", "-stream_loop", "-1", "-i", videoPath,
		"-c", "copy", "-f", "rtsp", rtspURL,
	)
	cmd.Stdout = testWriter{t}
	cmd.Stderr = testWriter{t}
	if err := cmd.Start(); err != nil {
		t.Fatalf("error starting ffmpeg push: %v", err)
	}

	time.Sleep(300 * time.Millisecond)
}

func waitForPort(t *testing.T, addr string, timeout time.Duration) {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		conn, err := net.DialTimeout("udp", addr, 100*time.Millisecond)
		if err == nil {
			conn.Close()
			return

		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("timeout out waiting for %s to be ready", addr)
}

func startMediaMtx(t *testing.T, port int) {
	cfgPath := fmt.Sprintf("%s/mediamtx.yml", t.TempDir())
	cfg := fmt.Sprintf("rtspAddress: :%d\npaths:\n  all_others:\n", port)
	if err := os.WriteFile(cfgPath, []byte(cfg), 0644); err != nil {
		t.Fatalf("error writing mediamtx config: %v", err)
	}

	cmd := exec.CommandContext(t.Context(), "mediamtx", cfgPath)
	cmd.Stdout = testWriter{t}
	cmd.Stderr = testWriter{t}
	if err := cmd.Start(); err != nil {
		t.Fatalf("error starting mediamtx: %v", err)
	}

	waitForPort(t, fmt.Sprintf("127.0.0.1:%d", port), 2*time.Second)
}

func startRTSPServer(t *testing.T, videoPath string) string {
	streamPath := "live"
	port := getFreePort(t)
	startMediaMtx(t, port)
	pushTestVideo(t, videoPath, port, streamPath)

	return fmt.Sprintf("rtsp://127.0.0.1:%d/%s", port, streamPath)
}

func TestStreamingRTSP(t *testing.T) {
	if _, err := exec.LookPath("mediamtx"); err != nil {
		if errors.Is(err, exec.ErrNotFound) {
			t.Skip("mediamtx binary not found")
		} else {
			t.Fatalf("error looking for mediamtx binary: %v", err)
		}
	}

	videoPath := fmt.Sprintf("%s/%s", t.TempDir(), testVideoFilename)
	generateTestVideo(t, videoPath, testWidth, testHeight, testFPS, testDuration)

	rtspURL := startRTSPServer(t, videoPath)
	testStreaming(t, rtspURL, 10*time.Second)
}

func TestStreamingFromFile(t *testing.T) {
	videoPath := fmt.Sprintf("%s/%s", t.TempDir(), testVideoFilename)
	generateTestVideo(t, videoPath, testWidth, testHeight, testFPS, testDuration)
	testStreaming(t, videoPath, 1*time.Second)
}

func generateTestVideo(t *testing.T, path string, width, height, fps, duration int) {
	cmd := exec.Command(
		"ffmpeg",
		"-f", "lavfi",
		"-i", fmt.Sprintf("testsrc=size=%dx%d:rate=%d:duration=%d", width, height, fps, duration),
		"-c:v", "libx264",
		"-pix_fmt", "yuv420p",
		"-y", path,
	)
	_, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("error generating test video: %v", err)
	}
	t.Log("generated test video successfully")
}

func newMockDriverConn(t *testing.T, streamURL string) (*grpc.ClientConn, error) {
	lis := bufconn.Listen(bufConnSize)
	s := grpc.NewServer()
	driver_pb.RegisterStreamServiceServer(s, &mockStreamSvc{url: streamURL, t: t})
	go s.Serve(lis)
	t.Cleanup(s.Stop)

	conn, _ := grpc.NewClient("passthrough:///bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return lis.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	t.Cleanup(func() { conn.Close() })

	return conn, nil
}

type mockStreamSvc struct {
	driver_pb.UnimplementedStreamServiceServer
	url string
	t   *testing.T
}

func (s *mockStreamSvc) GetVideoStreamURL(ctx context.Context, req *driver_pb.GetVideoStreamURLRequest) (*driver_pb.GetVideoStreamURLResponse, error) {
	s.t.Log("mock stream service received request for video stream URL")
	resp := driver_pb.GetVideoStreamURLResponse{StreamUrl: s.url}
	return &resp, nil
}
