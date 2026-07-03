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

const (
	testWidth         = 320
	testHeight        = 240
	testFPS           = 10
	testDuration      = 3
	testVideoFilename = "test.mp4"
	minFrames         = testFPS
	testTimeout       = 15 * time.Second
)

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

func TestStreamingFromFile(t *testing.T) {
	videoPath := fmt.Sprintf("%s/%s", t.TempDir(), testVideoFilename)
	generateTestVideo(t, videoPath, testWidth, testHeight, testFPS, testDuration)
	testStreaming(t, videoPath)
}

func testStreaming(t *testing.T, inputFileURL string) {
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
