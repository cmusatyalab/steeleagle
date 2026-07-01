package vehicle_test

import (
	"context"
	"fmt"
	"net"
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

type testWriter struct{ t *testing.T }

func (tw testWriter) Write(p []byte) (n int, err error) {
	tw.t.Log(string(p))
	return len(p), nil
}

const (
	testWidth         = 320
	testHeight        = 240
	testFPS           = 10
	testDuration      = 3
	testBufCap        = 2
	testVideoFilename = "test.mp4"
	minFrames         = testFPS * testDuration
	bufConnSize       = 1 << 20
)

func TestStreaming(t *testing.T) {
	videoPath := fmt.Sprintf("%s/%s", t.TempDir(), testVideoFilename)
	generateTestVideo(t, videoPath, testWidth, testHeight, testFPS, testDuration)
	driverConn, err := newMockDriverConn(t, videoPath)
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

	time.Sleep(time.Second)

	select {
	case err = <-errCh:
		t.Fatalf("error with video stream: %v", err)
	default:
	}

	if numFrames < minFrames {
		t.Fatalf("only received %d frames", numFrames)
	}
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
