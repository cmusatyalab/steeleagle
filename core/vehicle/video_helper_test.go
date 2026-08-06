package vehicle_test

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Constants defining the test video characteristics.
const (
	testWidth         = 320
	testHeight        = 240
	testFPS           = 10
	testDuration      = 3
	testVideoFilename = "test.mp4"
)

// generateTestVideo creates a synthetic video stream.
func generateTestVideo(t *testing.T, path string, width, height, fps, duration int) {
	t.Helper()
	cmd := exec.Command(
		"ffmpeg",
		"-f", "lavfi",
		"-i", fmt.Sprintf("testsrc=size=%dx%d:rate=%d:duration=%d", width, height, fps, duration),
		"-c:v", "libx264",
		"-g", "1", // keyframe on every frame, so a client joining the looped stream at any point can decode immediately
		"-pix_fmt", "yuv420p",
		"-y", path,
	)
	_, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("error generating test video: %v", err)
	}
	t.Log("generated test video successfully")
}

// getFreePort finds a free port to host on.
func getFreePort(t *testing.T) int {
	t.Helper()
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("error finding free port: %v", err)
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port
}

// pushTestVideo pipes a video to an RTSP stream to an RTSP server.
func pushTestVideo(t *testing.T, videoPath string, port int, path string) {
	t.Helper()
	rtspURL := fmt.Sprintf("rtsp://127.0.0.1:%d/%s", port, path)
	cmd := exec.CommandContext(t.Context(), "ffmpeg",
		"-re", "-stream_loop", "-1", "-i", videoPath,
		"-c", "copy", "-f", "rtsp", rtspURL,
	)
	if err := cmd.Start(); err != nil {
		t.Fatalf("error starting ffmpeg push: %v", err)
	}
}

// waitForPort waits for a port to be ready.
func waitForPort(t *testing.T, addr string, timeout time.Duration) {
	t.Helper()
	start := time.Now()
	deadline := start.Add(timeout)
	for time.Now().Before(deadline) {
		conn, err := net.DialTimeout("tcp", addr, 100*time.Millisecond)
		if err == nil {
			conn.Close()
			t.Logf("waiting for port took %s time", time.Since(start))
			return

		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("timeout out waiting for %s to be ready", addr)
}

// startMediaMtx starts the MediaMtx RTSP server.
func startMediaMtx(t *testing.T, port int) {
	t.Helper()
	cfgPath := fmt.Sprintf("%s/mediamtx.yml", t.TempDir())
	cfg := fmt.Sprintf("rtspAddress: :%d\npaths:\n  all_others:\n", port)
	if err := os.WriteFile(cfgPath, []byte(cfg), 0644); err != nil {
		t.Fatalf("error writing mediamtx config: %v", err)
	}

	cmd := exec.CommandContext(t.Context(), "mediamtx", cfgPath)
	if err := cmd.Start(); err != nil {
		t.Fatalf("error starting mediamtx: %v", err)
	}

	waitForPort(t, fmt.Sprintf("127.0.0.1:%d", port), 2*time.Second)
}

// startRTSPServer gets a free port and pipes a test video to a MediaMtx RTSP
// server on that port.
func startRTSPServer(t *testing.T, videoPath string) string {
	t.Helper()
	streamPath := "live"
	port := getFreePort(t)
	startMediaMtx(t, port)
	pushTestVideo(t, videoPath, port, streamPath)

	return fmt.Sprintf("rtsp://127.0.0.1:%d/%s", port, streamPath)
}

// testStreaming tests the driver streaming service exchange with the vehicle
// data service.
func testStreaming(t *testing.T, inputFileURL string) {
	driverPlugin, _, _, _, err := setupPlugins(t, inputFileURL)
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}
	pluginCfg := vehicle.PluginConfig{Driver: driverPlugin}
	videoCfg := vehicle.VideoStreamConfig{Resolution: vehicle.Res720P}
	if len(inputFileURL) == 0 {
		videoCfg.StreamType = vehicle.Frames
	}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}}).With().Timestamp().Logger()
	v, err := vehicle.NewVehicle(
		pluginCfg,
		vehicle.WithVideoStreamConfig(videoCfg),
		vehicle.WithLogger(logger),
	)
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}

	err = v.Start(t.Context())
	if err != nil {
		t.Fatalf("couldn't start vehicle: %v", err)
	}

	target := filepath.Join("unix://", v.RunDir, vehicle.MainSocketName)
	t.Logf("target: %s", target)
	conn, err := grpc.NewClient(
		target,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("error creating vehicle client: %v", err)
	}
	client := vehiclepb.NewDataServiceClient(conn)

	now := time.Now()
	var resp *vehiclepb.GetFrameResponse
	for {
		if time.Since(now) > 5*time.Second {
			t.Fatal("timed out waiting for frame")
		}
		ctx, cancel := context.WithTimeout(t.Context(), time.Second)
		resp, err = client.GetFrame(ctx, &vehiclepb.GetFrameRequest{})
		if ctx.Err() != nil {
			t.Fatalf("timeout out waiting to get frame from vehicle")
		}
		cancel()
		if err != nil {
			t.Logf("received error %v getting frame from vehicle", err)
			time.Sleep(100 * time.Millisecond)
			continue
		}
		if resp == nil {
			time.Sleep(100 * time.Millisecond)
			continue
		}
		if resp.GetFrame() == nil {
			time.Sleep(100 * time.Millisecond)
			continue
		}
		break
	}
	if resp.GetFrame().GetId() == 0 {
		t.Error("frame id not set")
	}
	if resp.GetFrame().GetTimestamp() == nil {
		t.Error("timestamp is nil")
	}
	if len(resp.GetFrame().GetEncodedData()) == 0 {
		t.Error("frame data not present")
	}
}
