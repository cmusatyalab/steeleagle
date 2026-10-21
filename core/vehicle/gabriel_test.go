package vehicle

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	gabriel "github.com/cmusatyalab/gabriel/go"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/prometheus/client_golang/prometheus/testutil"
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
		{"driver's raw frames", GabrielConfig{
			Flow: GabrielFlow{Producers: []GabrielProducer{{Name: GabrielRawFramesProducer}}, Engines: []GabrielEngine{local}},
		}, true},
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
	recordDir := t.TempDir()
	v := &Vehicle{
		Name:  fmt.Sprintf("test%d", os.Getpid()),
		store: store,
		log:   zerolog.New(io.Discard),
		gabrielCfg: GabrielConfig{
			Flow: GabrielFlow{
				Producers: []GabrielProducer{{Name: GabrielFramesProducer}},
				Engines:   []GabrielEngine{{Name: "{vehicle}.detector", Location: GabrielLocal}},
				Edges: []GabrielEdge{
					{From: GabrielFramesProducer, To: "{vehicle}.detector", Timeout: "1s"},
				},
			},
			RecordDir: recordDir,
		},
	}
	engineName := v.Name + ".detector"
	ctx, cancel := context.WithCancel(t.Context())
	defer cancel()

	detections := resultpb.DetectionResult_builder{Detections: []*resultpb.Detection{
		resultpb.Detection_builder{ClassName: "person", Score: 0.9}.Build(),
	}}.Build()
	engineErr := make(chan error, 1)
	frameType := string((*telemetrypb.EncodedFrame)(nil).ProtoReflect().Descriptor().FullName())
	go func() { engineErr <- runTestDetector(ctx, engineName, frameType, detections) }()

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
	producer := v.Name + ".frames"
	if got := testutil.ToFloat64(gabrielOutcomes.WithLabelValues(producer, engineName, outcomeResult)); got < 1 {
		t.Errorf("results counted = %v, want at least 1", got)
	}
	if got := testutil.CollectAndCount(gabrielInputLatency); got < 1 {
		t.Error("no result latency was recorded")
	}

	// The recording is closed once the flow stops, after cancel.
	recordings, err := filepath.Glob(filepath.Join(recordDir, "*", gabrielEventsFile))
	if err != nil || len(recordings) != 1 {
		t.Fatalf("recordings = %v, %v, want one", recordings, err)
	}
	deadline = time.Now().Add(gabrielTestWait)
	for !slices.ContainsFunc(readCSV(t, recordings[0]), func(row []string) bool {
		return row[0] == "Result" && row[5] == engineName
	}) {
		if time.Now().After(deadline) {
			t.Fatal("no result was recorded")
		}
		time.Sleep(gabrielTestPoll)
	}
}

// TestGabrielFlowTakesDriverFrames runs a flow on the driver's raw frames,
// whose producer starts after the flow, as a driver's would.
func TestGabrielFlowTakesDriverFrames(t *testing.T) {
	store, err := newDataStore(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	v := &Vehicle{
		// Not the other tests' name: their servers may still be closing.
		Name:  fmt.Sprintf("driver%d", os.Getpid()),
		store: store,
		log:   zerolog.New(io.Discard),
		gabrielCfg: GabrielConfig{
			Flow: GabrielFlow{
				Producers: []GabrielProducer{{Name: GabrielRawFramesProducer}},
				Engines:   []GabrielEngine{{Name: "{vehicle}.detector", Location: GabrielLocal}},
				Edges: []GabrielEdge{
					{From: GabrielRawFramesProducer, To: "{vehicle}.detector", Timeout: "1s"},
				},
			},
		},
	}
	engineName := v.Name + ".detector"
	ctx, cancel := context.WithCancel(t.Context())
	defer cancel()

	detections := resultpb.DetectionResult_builder{Detections: []*resultpb.Detection{
		resultpb.Detection_builder{ClassName: "person", Score: 0.9}.Build(),
	}}.Build()
	engineErr := make(chan error, 1)
	frameType := string((*telemetrypb.RawFrame)(nil).ProtoReflect().Descriptor().FullName())
	go func() { engineErr <- runTestDetector(ctx, engineName, frameType, detections) }()

	if err := v.startGabriel(ctx); err != nil {
		t.Fatalf("startGabriel: %v", err)
	}

	// The driver.
	producer, err := gabriel.NewProducer(v.Name+".raw_frames", frameType, gabrielTestMaxResultSize)
	if err != nil {
		t.Fatal(err)
	}
	defer producer.Close()
	frame, err := proto.Marshal(telemetrypb.RawFrame_builder{Data: []byte("rgb"), HRes: 1, VRes: 1, Channels: 3}.Build())
	if err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(gabrielTestWait)
	for {
		// The flow may still be installing, so send frames until one is
		// answered.
		if _, err := producer.Send(v.Name, frame); err != nil {
			t.Fatalf("sending a frame: %v", err)
		}
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

// runTestDetector is an engine that answers each input of frameType with
// detections, until ctx ends.
func runTestDetector(ctx context.Context, name, frameType string, detections *resultpb.DetectionResult) error {
	resultType := string(detections.ProtoReflect().Descriptor().FullName())
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
		if err := engine.Drop(result); err != nil {
			return err
		}
	}
}

func TestLogGabrielDetections(t *testing.T) {
	event := gabriel.Event{
		Kind:    gabriel.EventResult,
		ID:      gabriel.InputID{Seq: 7},
		Engine:  "harpy.yolo",
		Outcome: gabriel.OutcomeForward,
	}
	result := resultpb.DetectionResult_builder{
		Detections: []*resultpb.Detection{resultpb.Detection_builder{
			ClassName: "person",
			Score:     0.875,
			Bbox: resultpb.BoundingBox_builder{
				XMin: 0.1, YMin: 0.2,
				XMax: 0.3, YMax: 0.4,
			}.Build(),
		}.Build()},
	}.Build()
	const want = `{"level":"debug","engine":"harpy.yolo","seq":7,"outcome":"forward",` +
		`"detections":["person 0.88 [0.10,0.20 0.30,0.40]"],"message":"gabriel detections"}` + "\n"

	var out bytes.Buffer
	logGabrielDetections(zerolog.New(&out).Level(zerolog.DebugLevel), event, result)
	if out.String() != want {
		t.Errorf("logged %s, want %s", out.String(), want)
	}

	out.Reset()
	logGabrielDetections(zerolog.New(&out).Level(zerolog.InfoLevel), event, result)
	if out.Len() != 0 {
		t.Errorf("logged %s at info level, want nothing", out.String())
	}
}
