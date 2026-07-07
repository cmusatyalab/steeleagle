package vehicle_test

import (
	"errors"
	"fmt"
	"os/exec"
	"testing"
	"time"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog"
)

func TestStreamingFromFile(t *testing.T) {
	videoPath := fmt.Sprintf("%s/%s", t.TempDir(), testVideoFilename)
	generateTestVideo(t, videoPath, testWidth, testHeight, testFPS, testDuration)
	testStreaming(t, videoPath)
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
	time.Sleep(500 * time.Millisecond)

	testStreaming(t, rtspURL)
}
