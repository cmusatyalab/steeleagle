package vehicle_test

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"testing"
	"time"
)

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
}

func waitForPort(t *testing.T, addr string, timeout time.Duration) {
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
