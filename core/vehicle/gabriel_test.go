package vehicle

import (
	"context"
	"fmt"
	"io"
	"os"
	"testing"
	"time"

	gabriel "github.com/cmusatyalab/gabriel/go"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/rs/zerolog"
	"google.golang.org/protobuf/proto"
)

const (
	// gabrielTestWait is far longer than anything here takes, so a test fails
	// rather than hangs.
	gabrielTestWait = 5 * time.Second
	// gabrielTestPoll is how often a test pushes a frame and checks for its
	// result.
	gabrielTestPoll = 20 * time.Millisecond
	// gabrielTestMaxResultSize fits the test engine's results.
	gabrielTestMaxResultSize = 4096
)

func TestGabrielConfigValidate(t *testing.T) {
	local := GabrielEngine{Name: "{vehicle}.yolo", Location: GabrielLocal}
	remote := GabrielEngine{Name: "detector", Location: GabrielRemote}
	frames := []GabrielProducer{{Name: GabrielFramesProducer}}
	tests := []struct {
		name  string
		cfg   GabrielConfig
		valid bool
	}{
		{"no flow", GabrielConfig{}, true},
		{"local flow", GabrielConfig{Flow: GabrielFlow{Producers: frames, Engines: []GabrielEngine{local}}}, true},
		{"remote flow with a server", GabrielConfig{
			Flow:              GabrielFlow{Producers: frames, Engines: []GabrielEngine{remote}},
			RemoteServer:      "127.0.0.1:4433",
			RemoteCertificate: []byte{1},
		}, true},
		{"remote flow without a server", GabrielConfig{
			Flow: GabrielFlow{Producers: frames, Engines: []GabrielEngine{remote}},
		}, false},
		{"producer that is not a stream", GabrielConfig{
			Flow: GabrielFlow{Producers: []GabrielProducer{{Name: "camera"}}},
		}, false},
		{"engine with no location", GabrielConfig{
			Flow: GabrielFlow{Producers: frames, Engines: []GabrielEngine{{Name: "yolo"}}},
		}, false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if err := test.cfg.Validate(); (err == nil) != test.valid {
				t.Fatalf("Validate() = %v, want valid %v", err, test.valid)
			}
		})
	}
}

func TestGabrielFlowForVehicle(t *testing.T) {
	flow := GabrielFlow{
		Producers: []GabrielProducer{{Name: GabrielFramesProducer, Tokens: 2}},
		Engines:   []GabrielEngine{{Name: "{vehicle}.yolo", Location: GabrielLocal}},
		Edges:     []GabrielEdge{{From: GabrielFramesProducer, To: "{vehicle}.yolo", Timeout: "1s"}},
	}
	got := flow.forVehicle("harpy")
	if got.Producers[0] != (GabrielProducer{Name: "harpy.frames", Tokens: 2}) ||
		got.Engines[0] != (GabrielEngine{Name: "harpy.yolo", Location: GabrielLocal}) ||
		got.Edges[0] != (GabrielEdge{From: "harpy.frames", To: "harpy.yolo", Timeout: "1s"}) {
		t.Fatalf("forVehicle(harpy) = %+v", got)
	}
	if flow.Producers[0].Name != GabrielFramesProducer {
		t.Fatal("forVehicle changed the flow it was called on")
	}
}

// TestGabrielFlowStoresResults runs a vehicle's flow end to end on this
// machine: frames from the store go to a test engine, and its detections come
// back to the store. Gabriel's names are global to the machine, so the
// vehicle's name includes the process id.
func TestGabrielFlowStoresResults(t *testing.T) {
	store, err := newDataStore(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	v := &Vehicle{
		Name:  fmt.Sprintf("test%d", os.Getpid()),
		store: store,
		log:   zerolog.New(io.Discard),
		gabrielCfg: GabrielConfig{Flow: GabrielFlow{
			Producers: []GabrielProducer{{Name: GabrielFramesProducer}},
			Engines:   []GabrielEngine{{Name: "{vehicle}.detector", Location: GabrielLocal}},
			Edges: []GabrielEdge{
				{From: GabrielFramesProducer, To: "{vehicle}.detector", Timeout: "1s"},
			},
		}},
	}
	engineName := v.Name + ".detector"
	ctx, cancel := context.WithCancel(t.Context())
	defer cancel()

	detections := resultpb.DetectionResult_builder{Detections: []*resultpb.Detection{
		resultpb.Detection_builder{ClassName: "person", Score: 0.9}.Build(),
	}}.Build()
	engineErr := make(chan error, 1)
	go func() { engineErr <- runTestDetector(ctx, engineName, detections) }()

	if err := v.startGabriel(ctx); err != nil {
		t.Fatalf("startGabriel: %v", err)
	}

	frame := telemetrypb.EncodedFrame_builder{EncodedData: []byte("jpeg")}.Build()
	deadline := time.Now().Add(gabrielTestWait)
	for {
		// The flow may still be installing, so push frames until one is
		// answered.
		store.addFrame(frame)
		if result := store.getLatestResult(engineName); result != nil {
			if !proto.Equal(result.GetDetectionResult(), detections) {
				t.Fatalf("stored %v, want detections %v", result, detections)
			}
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("no result was stored")
		}
		time.Sleep(gabrielTestPoll)
	}
	cancel()
	if err := <-engineErr; err != nil {
		t.Fatal(err)
	}
}

// runTestDetector is an engine that answers each EncodedFrame with
// detections, until ctx ends.
func runTestDetector(ctx context.Context, name string, detections *resultpb.DetectionResult) error {
	resultType := string(detections.ProtoReflect().Descriptor().FullName())
	frameType := string((*telemetrypb.EncodedFrame)(nil).ProtoReflect().Descriptor().FullName())
	result, err := proto.Marshal(detections)
	if err != nil {
		return err
	}
	engine, err := gabriel.NewEngine(name, resultType, gabrielTestMaxResultSize)
	if err != nil {
		return err
	}
	defer engine.Close()
	for {
		input, err := engine.Next(ctx)
		if err != nil {
			return nil // ctx ended
		}
		if input.PayloadType != frameType {
			return fmt.Errorf("engine got an input of type %q, want %q", input.PayloadType, frameType)
		}
		if err := engine.Stop(result); err != nil {
			return err
		}
	}
}
