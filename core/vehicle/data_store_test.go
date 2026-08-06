package vehicle

import (
	"testing"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"google.golang.org/protobuf/types/known/timestamppb"
)

func newTestDataStore(t *testing.T) *dataStore {
	t.Helper()
	store, err := newDataStore(t.TempDir())
	if err != nil {
		t.Fatalf("couldn't create data store: %v", err)
	}
	if err := store.init(t.Context()); err != nil {
		t.Fatalf("couldn't init data store: %v", err)
	}
	return store
}

func TestGetLatestTelemetryEmpty(t *testing.T) {
	store := newTestDataStore(t)
	if tel := store.getLatestTelemetry(); tel != nil {
		t.Fatalf("expected nil telemetry, got %v", tel)
	}
}

func TestAddAndGetLatestTelemetry(t *testing.T) {
	store := newTestDataStore(t)
	tel := telemetrypb.Telemetry_builder{Timestamp: timestamppb.Now()}.Build()
	store.addTelemetry(tel)

	if got := store.getLatestTelemetry(); got != tel {
		t.Fatalf("expected %v, got %v", tel, got)
	}
}

func TestGetLatestFrameEmpty(t *testing.T) {
	store := newTestDataStore(t)
	if frame := store.getLatestFrame(); frame != nil {
		t.Fatalf("expected nil frame, got %v", frame)
	}
}

func TestAddAndGetLatestFrame(t *testing.T) {
	store := newTestDataStore(t)
	frame := telemetrypb.EncodedFrame_builder{Id: 42}.Build()
	store.addFrame(frame)

	if got := store.getLatestFrame(); got != frame {
		t.Fatalf("expected %v, got %v", frame, got)
	}
}

func TestGetLatestResultEmpty(t *testing.T) {
	store := newTestDataStore(t)
	if res := store.getLatestResult("producer"); res != nil {
		t.Fatalf("expected nil result, got %v", res)
	}
}

func TestAddAndGetLatestResult(t *testing.T) {
	store := newTestDataStore(t)
	res := resultpb.ComputeResult_builder{Timestamp: timestamppb.Now()}.Build()
	store.addResult("producer", res)

	if got := store.getLatestResult("producer"); got != res {
		t.Fatalf("expected %v, got %v", res, got)
	}
	if got := store.getLatestResult("other"); got != nil {
		t.Fatalf("expected nil result for unknown producer, got %v", got)
	}
}

func TestSubscribeToTelemetry(t *testing.T) {
	store := newTestDataStore(t)
	ch := store.subscribeToTelemetry()

	tel := telemetrypb.Telemetry_builder{Timestamp: timestamppb.Now()}.Build()
	store.addTelemetry(tel)

	select {
	case got := <-ch:
		if got != tel {
			t.Fatalf("expected %v, got %v", tel, got)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out waiting for telemetry")
	}
}

func TestSubscribeToFrames(t *testing.T) {
	store := newTestDataStore(t)
	ch := store.subscribeToFrames()

	frame := telemetrypb.EncodedFrame_builder{Id: 7}.Build()
	store.addFrame(frame)

	select {
	case got := <-ch:
		if got != frame {
			t.Fatalf("expected %v, got %v", frame, got)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out waiting for frame")
	}
}

func TestItob(t *testing.T) {
	a := itob(1)
	b := itob(2)
	if len(a) != 8 {
		t.Fatalf("expected 8 byte representation, got %d bytes", len(a))
	}
	// Big endian representation should preserve numeric ordering
	// lexicographically.
	if string(a) >= string(b) {
		t.Fatalf("expected itob(1) < itob(2) lexicographically")
	}
}
