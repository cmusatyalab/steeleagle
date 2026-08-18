package vehicle_test

import (
	"errors"
	"fmt"
	"os/exec"
	"testing"
)

func TestStreamingFromFile(t *testing.T) {
	requireFFmpegFpsMode(t)

	videoPath := fmt.Sprintf("%s/%s", t.TempDir(), testVideoFilename)
	generateTestVideo(t, videoPath, testWidth, testHeight, testFPS, testDuration)
	testStreaming(t, videoPath)
}

func TestStreamingRTSP(t *testing.T) {
	requireFFmpegFpsMode(t)

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

	testStreaming(t, rtspURL)
}

func TestStreamingFrames(t *testing.T) {
	testStreaming(t, "")
}
