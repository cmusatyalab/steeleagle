package vehicle

import (
	"testing"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	steammsgpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/stream"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/protobuf/types/known/timestamppb"
)

func newTestDataService(t *testing.T) *DataService {
	t.Helper()
	return &DataService{store: newTestDataStore(t)}
}

func TestGetResultUnavailable(t *testing.T) {
	svc := newTestDataService(t)
	resp, err := svc.GetResult(t.Context(), &vehiclepb.GetResultRequest{Name: "producer"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Result != nil {
		t.Fatal("expected result to be nil")
	}
}

func TestGetResult(t *testing.T) {
	svc := newTestDataService(t)
	res := &resultpb.ComputeResult{Timestamp: timestamppb.Now()}
	svc.store.addResult("producer", res)

	resp, err := svc.GetResult(t.Context(), &vehiclepb.GetResultRequest{Name: "producer"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Result != res {
		t.Fatalf("expected %v, got %v", res, resp.Result)
	}
}

func TestGetTelemetryUnavailable(t *testing.T) {
	svc := newTestDataService(t)
	res, err := svc.GetTelemetry(t.Context(), &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.Telemetry != nil {
		t.Fatal("expected result to be nil")
	}
}

func TestGetTelemetry(t *testing.T) {
	svc := newTestDataService(t)
	tel := &steammsgpb.Telemetry{Timestamp: timestamppb.Now()}
	svc.store.addTelemetry(tel)

	resp, err := svc.GetTelemetry(t.Context(), &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Telemetry != tel {
		t.Fatalf("expected %v, got %v", tel, resp.Telemetry)
	}
}

func TestGetFrameUnavailable(t *testing.T) {
	svc := newTestDataService(t)
	res, err := svc.GetFrame(t.Context(), &vehiclepb.GetFrameRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.Frame != nil {
		t.Fatal("expected result to be nil")
	}
}

func TestGetFrame(t *testing.T) {
	svc := newTestDataService(t)
	frame := &steammsgpb.EncodedFrame{Id: 1}
	svc.store.addFrame(frame)

	resp, err := svc.GetFrame(t.Context(), &vehiclepb.GetFrameRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Frame != frame {
		t.Fatalf("expected %v, got %v", frame, resp.Frame)
	}
}
