package vehicle

import (
	"math"
	"testing"
	"time"

	gabriel "github.com/cmusatyalab/gabriel/go"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/testutil"
	dto "github.com/prometheus/client_model/go"
)

func TestGabrielMetricsCountsLateResults(t *testing.T) {
	const producer, engine, flow = "metrics-test.frames", "metrics-test.detector", "metrics-test"
	published := newPublishTimes(producer)
	metrics := newGabrielMetrics(published)
	start := gabriel.Timestamp(time.Hour)
	published.published(1, start)
	published.published(2, start)
	event := func(kind gabriel.EventKind, seq uint64, at time.Duration) gabriel.Event {
		return gabriel.Event{
			Kind:   kind,
			ID:     gabriel.InputID{Producer: producer, Seq: seq},
			Engine: engine,
			Flow:   flow,
			At:     start + gabriel.Timestamp(at),
		}
	}

	// Input 1 is answered in time, and input 2 after its offer timed out.
	metrics.record(event(gabriel.EventSent, 1, 0))
	metrics.record(event(gabriel.EventResult, 1, 100*time.Millisecond))
	metrics.record(event(gabriel.EventSent, 2, 0))
	metrics.record(event(gabriel.EventTimedOut, 2, time.Second))
	metrics.record(event(gabriel.EventResult, 2, 2*time.Second))

	for outcome, want := range map[string]float64{
		outcomeResult:     1,
		outcomeLateResult: 1,
		outcomeTimedOut:   1,
	} {
		got := testutil.ToFloat64(gabrielOutcomes.WithLabelValues(producer, engine, outcome))
		if got != want {
			t.Errorf("%s outcomes = %v, want %v", outcome, got, want)
		}
	}
	if got := testutil.ToFloat64(gabrielInputsSent.WithLabelValues(producer, engine)); got != 2 {
		t.Errorf("inputs sent = %v, want 2", got)
	}
	if got := testutil.ToFloat64(gabrielInputsPublished.WithLabelValues(producer)); got != 2 {
		t.Errorf("inputs published = %v, want 2", got)
	}
	if got := testutil.CollectAndCount(gabrielRemoteRoundTrip, "gabriel_remote_round_trip_seconds"); got != 0 {
		t.Errorf("a local engine has %d round trip series, want none", got)
	}
}

func TestGabrielMetricsRemoteRoundTrip(t *testing.T) {
	const producer, engine = "round-trip-test.frames", "detector"
	published := newPublishTimes(producer)
	metrics := newGabrielMetrics(published)
	start := gabriel.Timestamp(time.Hour)
	published.published(1, start)
	// The remote server's clock is a day ahead. The input reached it after
	// 30 ms, the engine took 50 ms, and the result came back 20 ms later.
	remote := start + gabriel.Timestamp(24*time.Hour)
	metrics.record(gabriel.Event{
		Kind:       gabriel.EventResult,
		ID:         gabriel.InputID{Producer: producer, Seq: 1},
		Engine:     engine,
		OfferedAt:  remote + gabriel.Timestamp(30*time.Millisecond),
		At:         remote + gabriel.Timestamp(80*time.Millisecond),
		ReceivedAt: start + gabriel.Timestamp(100*time.Millisecond),
	})

	const want = 0.05 // 30 ms up and 20 ms down
	histogram := &dto.Metric{}
	if err := gabrielRemoteRoundTrip.WithLabelValues(producer, engine).(prometheus.Histogram).Write(histogram); err != nil {
		t.Fatal(err)
	}
	if got := histogram.GetHistogram().GetSampleSum(); math.Abs(got-want) > 1e-9 {
		t.Errorf("round trip = %v s, want %v s", got, want)
	}
}

func TestRecentTimesForgetsOldTimes(t *testing.T) {
	times := newRecentTimes[int]()
	start := gabriel.Timestamp(time.Hour)
	times.put(1, start, start)
	later := start + gabriel.Timestamp(gabrielMetricsWindow)
	times.put(2, later, later)

	if _, ok := times.get(1); ok {
		t.Error("a time older than the window is still remembered")
	}
	if at, ok := times.take(2); !ok || at != later {
		t.Errorf("take(2) = %v, %v, want %v, true", at, ok, later)
	}
	if _, ok := times.get(2); ok {
		t.Error("a taken time is still remembered")
	}
}
