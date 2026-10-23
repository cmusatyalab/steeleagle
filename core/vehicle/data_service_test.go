package vehicle

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"github.com/adrg/xdg"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	bolt "go.etcd.io/bbolt"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// newDataTestVehicle creates a running vehicle with a fake driver that
// streams the cameras "front" and "rear", both primary, and "down", and whose
// local compute service is a Uriel server serving engine, a local detection
// engine. Uriel names are shared by every process on the machine, so they are
// made unique to this one.
func newDataTestVehicle(t *testing.T, engine string) *Vehicle {
	t.Helper()
	t.Setenv("XDG_RUNTIME_DIR", t.TempDir())
	t.Setenv("XDG_DATA_HOME", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)

	lcs := fmt.Sprintf("lcs-%d", os.Getpid())
	server, err := uriel.NewServer(lcs)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { server.Close() })
	if err := server.AddEngine(engine); err != nil {
		t.Fatal(err)
	}

	cfg := &config.PluginConfig{
		Plugin: config.PluginRoot{Name: "fake", Type: "driver"},
		Driver: &config.DriverCap{
			Cameras: []config.DriverCamera{
				{Name: "front", Primary: true},
				{Name: "rear", Primary: true},
				{Name: "down"},
			},
			Supported: config.DriverSupported{
				Services: []string{"steeleagle_protocol/v1/services/driver/StreamService"},
			},
		},
	}
	driver := &fakeDriver{streams: &fakeStreams{sock: filepath.Join(t.TempDir(), "driver.sock")}}
	engines := map[string]Engine{engine: {Result: DetectionResultType, Local: true}}
	v, err := NewVehicle(driver, cfg, WithName(fmt.Sprintf("vehicle-%d", os.Getpid())),
		WithLcs(lcs), WithAvailableEngines(engines), WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { v.Close() })
	ctx, cancel := context.WithCancel(context.Background())
	if err := v.Start(ctx, nil); err != nil {
		cancel()
		t.Fatal(err)
	}
	t.Cleanup(func() {
		cancel()
		waitTimeout(t, v)
	})
	return v
}

// waitStored waits until bucket holds n values.
func waitStored(t *testing.T, v *Vehicle, bucket string, n int) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	stored := 0
	for time.Now().Before(deadline) {
		v.db.View(func(tx *bolt.Tx) error {
			if b := tx.Bucket([]byte(bucket)); b != nil {
				stored = b.Stats().KeyN
			}
			return nil
		})
		if stored >= n {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("bucket %q holds %d values, want %d", bucket, stored, n)
}

// telemetryAt is telemetry identified by its timestamp, at seconds after the
// Unix epoch.
func telemetryAt(seconds int64) *telemetrypb.Telemetry {
	return telemetrypb.Telemetry_builder{Timestamp: timestamppb.New(time.Unix(seconds, 0))}.Build()
}

// TestTelemetryStored ensures that the telemetry the driver publishes is
// stored, and that the most recent is returned by default.
func TestTelemetryStored(t *testing.T) {
	v := newDataTestVehicle(t, fmt.Sprintf("unused-%d", os.Getpid()))
	producer, err := uriel.NewProducer(v.Name+"."+TelemetryProducerName, "", 256)
	if err != nil {
		t.Fatal(err)
	}
	defer producer.Close()
	for i := range int64(2) {
		data, _ := proto.Marshal(telemetryAt(i))
		if _, err := producer.Send(v.Name, data); err != nil {
			t.Fatal(err)
		}
		waitStored(t, v, TelemetryBucket, int(i)+1)
	}
	resp, err := v.GetTelemetry(context.Background(), &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if got := resp.GetTelemetry(); len(got) != 1 || !proto.Equal(got[0], telemetryAt(1)) {
		t.Errorf("got %v, want the most recent telemetry", got)
	}
}

// TestDataflowResultsStored ensures that the results of a dataflow's engines
// are stored under their name as ComputeResults of the engine's result type,
// with the sequence number of the input they are about and whether the engine
// is local, and that a dataflow can be replaced.
func TestDataflowResultsStored(t *testing.T) {
	engineName := fmt.Sprintf("detector-%d", os.Getpid())
	v := newDataTestVehicle(t, engineName)
	engine, err := uriel.NewEngine(engineName, "steeleagle_protocol/v1/messages/result/DetectionResult", 256)
	if err != nil {
		t.Fatal(err)
	}
	defer engine.Close()
	producer, err := uriel.NewProducer(v.Name+".front", "", 64)
	if err != nil {
		t.Fatal(err)
	}
	defer producer.Close()

	spec := func(timeout string) string {
		return fmt.Sprintf(`
[[producers]]
name = %q

[[engines]]
name = %q
location = "local"

[[edges]]
from = %q
to = %q
timeout = %q
`, "front", engineName, "front", engineName, timeout)
	}
	// The second dataflow replaces the first
	for i, timeout := range []string{"4s", "5s"} {
		req := vehiclepb.SetDataflowRequest_builder{Toml: []byte(spec(timeout))}.Build()
		if _, err := v.SetDataflow(context.Background(), req); err != nil {
			t.Fatalf("set dataflow %d: %v", i, err)
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	before := time.Now()
	var seq uint64
	for i := range 2 {
		if seq, err = producer.Send(v.Name, []byte("frame")); err != nil {
			t.Fatal(err)
		}
		if _, err := engine.Next(ctx); err != nil {
			t.Fatal(err)
		}
		detection := resultpb.DetectionResult_builder{Detections: []*resultpb.Detection{
			resultpb.Detection_builder{ClassName: fmt.Sprint(i)}.Build(),
		}}.Build()
		data, _ := proto.Marshal(detection)
		if err := engine.Drop(data); err != nil {
			t.Fatal(err)
		}
		waitStored(t, v, engineName, i+1)
	}

	req := vehiclepb.GetResultRequest_builder{Engine: engineName}.Build()
	resp, err := v.GetResult(context.Background(), req)
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.GetResult()) != 1 {
		t.Fatalf("got %d results, want the most recent", len(resp.GetResult()))
	}
	result := resp.GetResult()[0]
	if got := result.GetDetectionResult().GetDetections(); len(got) != 1 || got[0].GetClassName() != "1" {
		t.Errorf("got detections %v, want the second", got)
	}
	if result.GetSequenceNum() != seq {
		t.Errorf("got sequence number %d, want %d", result.GetSequenceNum(), seq)
	}
	if !result.GetLocal() {
		t.Error("got a remote result, want a local one")
	}
	if at := result.GetTimestamp().AsTime(); at.Before(before.Add(-time.Second)) || at.After(time.Now()) {
		t.Errorf("got timestamp %v, want one during the test", at)
	}
}

// TestGetResultInvalidEngine ensures that GetResult rejects names that are
// not engines, fails with NotFound for an engine that never produced a
// result, and returns no results for an engine that has none in range.
func TestGetResultInvalidEngine(t *testing.T) {
	v := newDataTestVehicle(t, fmt.Sprintf("unused-%d", os.Getpid()))
	for _, engine := range []string{"", TelemetryBucket} {
		req := vehiclepb.GetResultRequest_builder{Engine: engine}.Build()
		if _, err := v.GetResult(context.Background(), req); status.Code(err) != codes.InvalidArgument {
			t.Errorf("engine %q: got %v, want InvalidArgument", engine, err)
		}
	}

	req := vehiclepb.GetResultRequest_builder{Engine: "detector"}.Build()
	if _, err := v.GetResult(context.Background(), req); status.Code(err) != codes.NotFound {
		t.Errorf("unknown engine: got %v, want NotFound", err)
	}

	data, _ := proto.Marshal(&resultpb.ComputeResult{})
	if err := v.store("detector", time.Unix(1, 0), data); err != nil {
		t.Fatal(err)
	}
	req = vehiclepb.GetResultRequest_builder{
		Engine: "detector", TimeStart: timestamppb.New(time.Unix(2, 0)),
	}.Build()
	if resp, err := v.GetResult(context.Background(), req); err != nil || len(resp.GetResult()) != 0 {
		t.Errorf("engine without results in range: got %v, %v, want none", resp.GetResult(), err)
	}
}

// TestGetTelemetryNone ensures that GetTelemetry returns no telemetry, rather
// than an error, before any is received.
func TestGetTelemetryNone(t *testing.T) {
	v := newDataTestVehicle(t, fmt.Sprintf("unused-%d", os.Getpid()))
	resp, err := v.GetTelemetry(context.Background(), &vehiclepb.GetTelemetryRequest{})
	if err != nil || len(resp.GetTelemetry()) != 0 {
		t.Errorf("got %v, %v, want no telemetry", resp.GetTelemetry(), err)
	}
}

// TestSetDataflowInvalid ensures that an invalid dataflow, including one with
// an engine that isn't available or isn't at its location, is rejected.
func TestSetDataflowInvalid(t *testing.T) {
	engine := fmt.Sprintf("unused-%d", os.Getpid())
	v := newDataTestVehicle(t, engine)
	for _, spec := range []string{
		"not toml [",
		"[[engines]]\nname = \"e\"\nlocation = \"local\"",
		"[[engines]]\nname = \"e\"\nlocation = \"elsewhere\"",
		fmt.Sprintf("[[engines]]\nname = %q\nlocation = \"remote\"", engine),
		fmt.Sprintf("[[engines]]\nname = %q", engine),
		"[[edges]]\nfrom = \"nothing\"\nto = \"nowhere\"\ntimeout = \"1s\"",
		"[[producers]]\nname = \"missing\"",
		"[[producers]]\nname = \"front\"\n[[producers]]\nname = \"rear\"",
		"[[producers]]\nname = \"down\"\n[[producers]]\nname = \"down\"",
		"[[producers]]\nname = \"telemetry\"\n[[producers]]\nname = \"telemetry\"",
	} {
		req := vehiclepb.SetDataflowRequest_builder{Toml: []byte(spec)}.Build()
		_, err := v.SetDataflow(context.Background(), req)
		if status.Code(err) != codes.InvalidArgument {
			t.Errorf("spec %q: got %v, want InvalidArgument", spec, err)
		}
	}
}

// TestDataflowTelemetryProducer ensures that a dataflow can feed the
// vehicle's telemetry to an engine, without asking the driver for any camera,
// while the vehicle still stores the telemetry itself, and that the engine's
// results are stored like any other's.
func TestDataflowTelemetryProducer(t *testing.T) {
	engineName := fmt.Sprintf("monitor-%d", os.Getpid())
	v := newDataTestVehicle(t, engineName)
	engine, err := uriel.NewEngine(engineName, "steeleagle_protocol/v1/messages/result/DetectionResult", 256)
	if err != nil {
		t.Fatal(err)
	}
	defer engine.Close()
	producer, err := uriel.NewProducer(v.Name+"."+TelemetryProducerName, "", 256)
	if err != nil {
		t.Fatal(err)
	}
	defer producer.Close()

	spec := fmt.Sprintf(`
[[producers]]
name = "telemetry"

[[engines]]
name = %[1]q
location = "local"

[[edges]]
from = "telemetry"
to = %[1]q
timeout = "1s"
`, engineName)
	req := vehiclepb.SetDataflowRequest_builder{Toml: []byte(spec)}.Build()
	if _, err := v.SetDataflow(context.Background(), req); err != nil {
		t.Fatal(err)
	}
	if got := v.flow.producers; !slices.Equal(got, []string{v.Name + "." + TelemetryProducerName}) {
		t.Errorf("got producers %v, want the telemetry's fully qualified name", got)
	}
	streams := v.driver.obj.(*fakeDriver).streams
	if cameras, _ := streams.requests(); len(cameras) != 1 ||
		cameras[0].HasPrimary() || len(cameras[0].GetSecondaries()) > 0 {
		t.Errorf("got camera streams %v, want one request for no cameras", cameras)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	sent, _ := proto.Marshal(telemetryAt(7))
	if _, err := producer.Send(v.Name, sent); err != nil {
		t.Fatal(err)
	}
	input, err := engine.Next(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(input.Data, sent) {
		t.Errorf("engine got %x, want the telemetry sent", input.Data)
	}
	if input.ID.Producer != v.Name+"."+TelemetryProducerName {
		t.Errorf("engine got an input from %q, want the telemetry producer", input.ID.Producer)
	}
	// An empty result isn't stored, so it has a detection
	data, _ := proto.Marshal(resultpb.DetectionResult_builder{Detections: []*resultpb.Detection{
		resultpb.Detection_builder{ClassName: "low-battery"}.Build(),
	}}.Build())
	if err := engine.Drop(data); err != nil {
		t.Fatal(err)
	}
	waitStored(t, v, engineName, 1)
	waitStored(t, v, TelemetryBucket, 1)
}

// TestDataflowTelemetryUnsupported ensures that a dataflow with a telemetry
// producer is rejected when the driver doesn't stream telemetry, and that a
// driver with a camera named like the telemetry producer can't set dataflows.
func TestDataflowTelemetryUnsupported(t *testing.T) {
	v := newDataTestVehicle(t, fmt.Sprintf("unused-%d", os.Getpid()))
	spec := []byte("[[producers]]\nname = \"telemetry\"")
	cap := *v.Config.Driver
	v.Config.Driver = &config.DriverCap{
		Cameras:     cap.Cameras,
		Supported:   cap.Supported,
		Unsupported: config.DriverUnsupported{Methods: []string{StreamTelemetryMethod}},
	}
	req := vehiclepb.SetDataflowRequest_builder{Toml: spec}.Build()
	if _, err := v.SetDataflow(context.Background(), req); status.Code(err) != codes.InvalidArgument {
		t.Errorf("driver without telemetry: got %v, want InvalidArgument", err)
	}

	v.Config.Driver = &config.DriverCap{
		Cameras:   append(slices.Clone(cap.Cameras), config.DriverCamera{Name: TelemetryProducerName}),
		Supported: cap.Supported,
	}
	req = vehiclepb.SetDataflowRequest_builder{Toml: []byte("[[producers]]\nname = \"down\"")}.Build()
	if _, err := v.SetDataflow(context.Background(), req); status.Code(err) != codes.InvalidArgument {
		t.Errorf("camera named telemetry: got %v, want InvalidArgument", err)
	}
}

// TestDataflowStreams ensures that the driver is asked to stream telemetry
// when the vehicle starts, and the cameras of a dataflow, by their fully
// qualified names, when it is set, that setting the same dataflow again does
// nothing, and that GetFlow returns the current dataflow as it was set.
func TestDataflowStreams(t *testing.T) {
	engineName := fmt.Sprintf("detector-%d", os.Getpid())
	v := newDataTestVehicle(t, engineName)
	engine, err := uriel.NewEngine(engineName, "", 64)
	if err != nil {
		t.Fatal(err)
	}
	defer engine.Close()
	streams := v.driver.obj.(*fakeDriver).streams
	if _, telemetry := streams.requests(); !slices.Equal(telemetry, []string{v.Name + ".telemetry"}) {
		t.Errorf("got telemetry streams %v, want %s.telemetry", telemetry, v.Name)
	}
	assertFlow := func(step, want string) {
		t.Helper()
		resp, err := v.GetFlow(context.Background(), &vehiclepb.GetFlowRequest{})
		if err != nil || string(resp.GetToml()) != want {
			t.Errorf("%s: got flow %q, %v, want %q", step, resp.GetToml(), err, want)
		}
	}
	assertFlow("no dataflow", "")

	spec := fmt.Sprintf(`
[[producers]]
name = "front"

[[producers]]
name = "down"

[[engines]]
name = %[1]q
location = "local"

[[edges]]
from = "front"
to = %[1]q
timeout = "1s"

[[edges]]
from = "down"
to = %[1]q
timeout = "1s"
`, engineName)
	req := vehiclepb.SetDataflowRequest_builder{Toml: []byte(spec)}.Build()
	if _, err := v.SetDataflow(context.Background(), req); err != nil {
		t.Fatal(err)
	}
	want := driverpb.StreamCamerasRequest_builder{
		Primary: driverpb.CameraRequest_builder{Id: "front", Uri: v.Name + ".front"}.Build(),
		Secondaries: []*driverpb.CameraRequest{
			driverpb.CameraRequest_builder{Id: "down", Uri: v.Name + ".down"}.Build(),
		},
	}.Build()
	if cameras, _ := streams.requests(); len(cameras) != 1 || !proto.Equal(cameras[0], want) {
		t.Errorf("got camera streams %v, want %v", cameras, want)
	}
	if got := v.flow.producers; !slices.Equal(got, []string{v.Name + ".front", v.Name + ".down"}) {
		t.Errorf("got producers %v, want the cameras' fully qualified names", got)
	}
	assertFlow("dataflow set", spec)

	// Setting the same dataflow again does nothing, so the driver isn't asked
	// to stream again
	if _, err := v.SetDataflow(context.Background(), req); err != nil {
		t.Fatal(err)
	}
	if cameras, _ := streams.requests(); len(cameras) != 1 {
		t.Errorf("got %d camera streams after setting the same dataflow, want 1", len(cameras))
	}

	// A dataflow that fails to be set leaves the cameras of the current one
	invalid := "[[producers]]\nname = \"rear\""
	req = vehiclepb.SetDataflowRequest_builder{Toml: []byte(invalid)}.Build()
	if _, err := v.SetDataflow(context.Background(), req); status.Code(err) != codes.InvalidArgument {
		t.Fatalf("got %v, want InvalidArgument", err)
	}
	if cameras, _ := streams.requests(); len(cameras) != 3 || !proto.Equal(cameras[2], want) {
		t.Errorf("got camera streams %v, want the current dataflow's restored", cameras)
	}
	assertFlow("invalid dataflow", spec)
}
