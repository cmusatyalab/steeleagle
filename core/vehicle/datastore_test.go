package vehicle

import (
	"context"
	"testing"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	uriel "github.com/cmusatyalab/uriel/go"
	"google.golang.org/protobuf/proto"
)

// TestTelemetryStored checks that the telemetry the driver publishes is
// stored, and that the most recent is returned by default.
func TestTelemetryStored(t *testing.T) {
	v, _ := newTestVehicle(t)
	producer, err := uriel.NewProducer(v.streamInfo.telemetry, "", 256)
	if err != nil {
		t.Fatal(err)
	}
	defer producer.Close()
	for i := range int64(2) {
		data, _ := proto.Marshal(telemetrypb.Telemetry_builder{Timestamp: at(i)}.Build())
		if _, err := producer.Send(data); err != nil {
			t.Fatal(err)
		}
		waitStored(t, v, TelemetryBucket, int(i)+1)
	}
	resp, err := vehiclepb.NewDataServiceClient(v.conn).GetTelemetry(callCtx(t), &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if got := resp.GetTelemetry(); len(got) != 1 || got[0].GetTimestamp().GetSeconds() != 1 {
		t.Errorf("got %v, want the most recent telemetry", got)
	}
}

// TestResultsStored checks that the results of a dataflow's engine are
// stored, whether the flow is fed by a camera or by telemetry.
func TestResultsStored(t *testing.T) {
	for _, producer := range []string{"front", TelemetryProducerName} {
		t.Run(producer, func(t *testing.T) {
			v, _ := newTestVehicle(t)
			if err := setDataflow(t, v, flowToml(t, producer)); err != nil {
				t.Fatal(err)
			}
			expectResultStored(t, v, producer)
		})
	}
}

// expectResultStored sends an input on the vehicle's producer, has testEngine
// detect "cat" in it, and checks that the result is stored as a local
// detection.
func expectResultStored(t *testing.T, v *Vehicle, producer string) {
	t.Helper()
	engine, err := uriel.NewEngine(testEngine, DetectionResultType, 256)
	if err != nil {
		t.Fatal(err)
	}
	defer engine.Close()
	p, err := uriel.NewProducer(v.producerUri(producer), "", 256)
	if err != nil {
		t.Fatal(err)
	}
	defer p.Close()

	if _, err := p.Send([]byte("input")); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := engine.Next(ctx); err != nil {
		t.Fatal(err)
	}
	detection := resultpb.DetectionResult_builder{Detections: []*resultpb.Detection{
		resultpb.Detection_builder{ClassName: "cat"}.Build(),
	}}.Build()
	data, _ := proto.Marshal(detection)
	if err := engine.Drop(data); err != nil {
		t.Fatal(err)
	}
	waitStored(t, v, testEngine, 1)

	resp, err := vehiclepb.NewDataServiceClient(v.conn).GetResult(callCtx(t),
		vehiclepb.GetResultRequest_builder{Engine: testEngine}.Build())
	if err != nil {
		t.Fatal(err)
	}
	got := resp.GetResult()
	if len(got) != 1 || !got[0].GetLocal() || !proto.Equal(got[0].GetDetectionResult(), detection) {
		t.Errorf("got results %v, want a local detection of a cat", got)
	}
}
