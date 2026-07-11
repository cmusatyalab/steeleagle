package vehicle_test

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"testing"
	"time"

    "github.com/cmusatyalab/steeleagle/core/vehicle"
)

// Constants defining the test video characteristics.
const (
	testWidth         = 320
	testHeight        = 240
	testFPS           = 10
	testDuration      = 3
	testVideoFilename = "test.mp4"
	minFrames         = 2
	testTimeout       = 15 * time.Second
)

// generateTestVideo creates a synthetic video stream.
func generateTestVideo(t *testing.T, path string, width, height, fps, duration int) {
    t.Helper()
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

// getFreePort finds a free port to host on.
func getFreePort(t *testing.T) int {
    t.Helper()
	l, err := net.ListenPacket("udp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("error finding free port: %v", err)
	}
	defer l.Close()
	return l.LocalAddr().(*net.UDPAddr).Port
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
		conn, err := net.DialTimeout("udp", addr, 100*time.Millisecond)
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

// testStreaming tests the driver streaming service exchange with the
// vehicle data service.
func testStreaming(t *testing.T, inputFileURL string) {
    driverPlugin, _, err := setupPlugins(t)
    if err != nil {
        t.Fatalf("couldn't create plugin config: %v", err)
    }
	pluginCfg := vehicle.PluginConfig{Driver: driverPlugin}
	resolution := driver_pb.GetVideoStreamURLRequest_RESOLUTION_720P
	videoCfg := vehicle.VideoStreamConfig{Resolution: resolution}
	v, err := vehicle.NewVehicle(pluginCfg, vehicle.WithServerListener(serverLn), vehicle.WithVideoStreamConfig(videoCfg))
	if err != nil {
		t.Fatalf("couldn't create vehicle")
	}

	numFrames := 0
	doneCh := make(chan struct{})
	handler := func(frame []byte) {
		numFrames += 1
		if numFrames == minFrames+1 {
			close(doneCh)
		}
	}

	errCh, err := v.StartRTSPVideoStream(t.Context(), videoCfg, handler)
	if err != nil {
		t.Fatalf("error starting video stream: %v", err)
	}

	select {
	case err = <-errCh:
		t.Fatalf("video stream error: %v", err)
	case <-doneCh:
	case <-time.After(testTimeout):
	}

	if numFrames < minFrames {
		t.Fatalf("only received %d frames", numFrames)
	}
}
