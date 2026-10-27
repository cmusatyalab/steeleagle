package vehicle

import (
	"bytes"
	"testing"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc/codes"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// flowToml is the TOML of flowOf(producers...).
func flowToml(t *testing.T, producers ...string) []byte {
	t.Helper()
	b, err := flowOf(producers...).ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// setDataflow sets the dataflow toml on v.
func setDataflow(t *testing.T, v *Vehicle, toml []byte) error {
	t.Helper()
	_, err := vehiclepb.NewDataServiceClient(v.conn).SetDataflow(callCtx(t),
		vehiclepb.SetDataflowRequest_builder{Toml: toml}.Build())
	return err
}

// expectFlow fails the test unless the current dataflow of v is toml.
func expectFlow(t *testing.T, v *Vehicle, toml []byte) {
	t.Helper()
	resp, err := vehiclepb.NewDataServiceClient(v.conn).GetFlow(callCtx(t), &vehiclepb.GetFlowRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(resp.GetToml(), toml) {
		t.Errorf("flow is %q, want %q", resp.GetToml(), toml)
	}
}

// TestSetDataflow checks that a dataflow streams its cameras and becomes the
// current one, that setting it again does nothing, and that it can be
// replaced.
func TestSetDataflow(t *testing.T) {
	v, driver := newTestVehicle(t)
	expectFlow(t, v, nil)

	first := flowToml(t, "front", "down")
	for range 2 {
		if err := setDataflow(t, v, first); err != nil {
			t.Fatal(err)
		}
	}
	expectFlow(t, v, first)
	want := []*driverpb.StreamCamerasRequest{driverpb.StreamCamerasRequest_builder{
		Primary:     cameraOf(v, "front"),
		Secondaries: []*driverpb.CameraRequest{cameraOf(v, "down")},
	}.Build()}
	expectCameras(t, driver, want)

	second := flowToml(t, TelemetryProducerName)
	if err := setDataflow(t, v, second); err != nil {
		t.Fatal(err)
	}
	expectFlow(t, v, second)
	expectCameras(t, driver, append(want, &driverpb.StreamCamerasRequest{}))
}

// TestSetDataflowInvalid checks that an invalid dataflow is refused before
// anything is streamed, and keeps the current one.
func TestSetDataflowInvalid(t *testing.T) {
	v, driver := newTestVehicle(t)
	current := flowToml(t, "down")
	if err := setDataflow(t, v, current); err != nil {
		t.Fatal(err)
	}
	for name, toml := range map[string][]byte{
		"malformed":        []byte("[[producers]"),
		"unknown key":      []byte("color = 'blue'"),
		"unknown producer": flowToml(t, "side"),
		"two primaries":    flowToml(t, "front", "rear"),
	} {
		expectCode(t, setDataflow(t, v, toml), codes.InvalidArgument)
		if n := len(driver.cameraRequests()); n != 1 {
			t.Errorf("%s: driver asked for cameras %d times, want once", name, n)
		}
		expectFlow(t, v, current)
	}
}

// TestSetDataflowAtomic checks that a dataflow Uriel refuses keeps the
// current one: its cameras are streamed again, and its results still stored.
func TestSetDataflowAtomic(t *testing.T) {
	v, driver := newTestVehicle(t)
	current := flowToml(t, "down")
	if err := setDataflow(t, v, current); err != nil {
		t.Fatal(err)
	}
	// The compute service doesn't serve the engine
	refused := flowOf("front")
	refused.Engines[0].Name = unique("missing")
	refused.Edges[0].To = refused.Engines[0].Name
	toml, err := refused.ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	expectCode(t, setDataflow(t, v, toml), codes.InvalidArgument)
	expectFlow(t, v, current)

	down := driverpb.StreamCamerasRequest_builder{
		Secondaries: []*driverpb.CameraRequest{cameraOf(v, "down")},
	}.Build()
	front := driverpb.StreamCamerasRequest_builder{Primary: cameraOf(v, "front")}.Build()
	expectCameras(t, driver, []*driverpb.StreamCamerasRequest{down, front, down})
	expectResultStored(t, v, "down")
}

// expectCameras fails the test unless the driver was asked for want.
func expectCameras(t *testing.T, driver *fakeDriver, want []*driverpb.StreamCamerasRequest) {
	t.Helper()
	got := driver.cameraRequests()
	if len(got) != len(want) {
		t.Fatalf("driver asked for cameras %v, want %v", got, want)
	}
	for i := range got {
		if !proto.Equal(got[i], want[i]) {
			t.Errorf("camera request %d is %v, want %v", i, got[i], want[i])
		}
	}
}

// storeAt stores m in bucket at seconds after the Unix epoch.
func storeAt(t *testing.T, v *Vehicle, bucket string, seconds int64, m proto.Message) {
	t.Helper()
	b, err := proto.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	if err := v.store(bucket, time.Unix(seconds, 0), b); err != nil {
		t.Fatal(err)
	}
}

// at is a timestamp at seconds after the Unix epoch.
func at(seconds int64) *timestamppb.Timestamp {
	return timestamppb.New(time.Unix(seconds, 0))
}

// TestGetTelemetry checks that telemetry is queried by time, that the most
// recent is returned without times, and that there is none at first.
func TestGetTelemetry(t *testing.T) {
	v, _ := newTestVehicle(t)
	client := vehiclepb.NewDataServiceClient(v.conn)
	resp, err := client.GetTelemetry(callCtx(t), &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.GetTelemetry()) != 0 {
		t.Errorf("got %v before any telemetry, want none", resp.GetTelemetry())
	}

	for i := range int64(4) {
		storeAt(t, v, TelemetryBucket, i+1, telemetrypb.Telemetry_builder{Timestamp: at(i + 1)}.Build())
	}
	for _, tc := range []struct {
		start, end *timestamppb.Timestamp
		want       []int64
	}{
		{nil, nil, []int64{4}},
		{at(2), at(3), []int64{2, 3}},
		{at(3), nil, []int64{3, 4}},
		{nil, at(2), []int64{1, 2}},
		{at(5), nil, nil},
	} {
		resp, err := client.GetTelemetry(callCtx(t),
			vehiclepb.GetTelemetryRequest_builder{TimeStart: tc.start, TimeEnd: tc.end}.Build())
		if err != nil {
			t.Fatal(err)
		}
		var got []int64
		for _, tm := range resp.GetTelemetry() {
			got = append(got, tm.GetTimestamp().GetSeconds())
		}
		if !equal(got, tc.want) {
			t.Errorf("query %v to %v got %v, want %v", tc.start.AsTime(), tc.end.AsTime(), got, tc.want)
		}
	}
}

// TestGetResult checks that results are queried by engine and time, that an
// engine without results has none, and that telemetry is not an engine.
func TestGetResult(t *testing.T) {
	v, _ := newTestVehicle(t)
	client := vehiclepb.NewDataServiceClient(v.conn)
	for i := range int64(3) {
		storeAt(t, v, testEngine, i+1, resultpb.ComputeResult_builder{Timestamp: at(i + 1)}.Build())
	}
	query := func(engine string, start, end *timestamppb.Timestamp) ([]int64, error) {
		resp, err := client.GetResult(callCtx(t),
			vehiclepb.GetResultRequest_builder{Engine: engine, TimeStart: start, TimeEnd: end}.Build())
		var got []int64
		for _, r := range resp.GetResult() {
			got = append(got, r.GetTimestamp().GetSeconds())
		}
		return got, err
	}
	if got, err := query(testEngine, nil, nil); err != nil || !equal(got, []int64{3}) {
		t.Errorf("latest result is %v (%v), want [3]", got, err)
	}
	if got, err := query(testEngine, at(1), at(2)); err != nil || !equal(got, []int64{1, 2}) {
		t.Errorf("results from 1 to 2 are %v (%v), want [1 2]", got, err)
	}
	if got, err := query("other", nil, nil); err != nil || len(got) != 0 {
		t.Errorf("results of an engine without any are %v (%v), want none", got, err)
	}
	for _, engine := range []string{"", TelemetryBucket} {
		_, err := query(engine, nil, nil)
		expectCode(t, err, codes.InvalidArgument)
	}
}

func equal(a, b []int64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
