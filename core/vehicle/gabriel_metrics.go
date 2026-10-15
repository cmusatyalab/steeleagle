package vehicle

// Prometheus metrics of the vehicle's Gabriel flow, for watching it live, e.g.
// during a flight. They come from the events about each producer's inputs.
// They are registered with the default registerer, so eagled serves them on
// /metrics when it is given a metrics port.
//
//   - gabriel_producer_inputs_published_total: inputs a producer published.
//   - gabriel_engine_inputs_sent_total: inputs sent to an engine.
//   - gabriel_engine_outcomes_total, by outcome: how an engine's offers
//     ended: result, late_result (after the offer timed out), skipped
//     (replaced by a newer input before it was sent) or timed_out.
//   - gabriel_client_input_processing_latency_seconds: from publishing an
//     input to its result from an engine, on this machine. This is how old
//     an engine's results are when the vehicle gets them.
//   - gabriel_engine_processing_latency_seconds: from sending an input to an
//     engine to its result, on the engine's machine.
//   - gabriel_engine_wait_seconds: from the offer to an engine to sending it
//     the input, i.e. how long the input waited for the engine to be free.
//   - gabriel_remote_round_trip_seconds: for a remote engine, the result
//     latency above minus the time from the offer to the result on the
//     remote server: the network both ways, and the waits on the vehicle. It
//     subtracts a time on one clock from a time on the other, so the clocks
//     need not agree. For an engine after another on the remote server, it
//     also counts the time on the remote server before its offer.
//   - gabriel_disconnects_total: lost connections to a server of the flow.
//   - gabriel_events_lost_total: events the vehicle missed, so the counts
//     above are short by up to that many.
//
// The labels are named producer_id and engine_id, as in the old Gabriel. The
// engine metrics have both, so an engine that two producers feed is counted
// for each.

import (
	"sync"
	"time"

	gabriel "github.com/cmusatyalab/gabriel/go"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

const (
	// gabrielMetricsWindow is how long the vehicle remembers when an input
	// was published or sent, waiting for its results. A late result can
	// still come after its offer timed out, so this is longer than any
	// engine's timeout.
	gabrielMetricsWindow = time.Minute

	outcomeResult     = "result"
	outcomeLateResult = "late_result"
	outcomeSkipped    = "skipped"
	outcomeTimedOut   = "timed_out"
)

// gabrielLatencyBuckets are histogram buckets, in seconds: from a local
// engine on the vehicle to a remote one over a slow link.
var gabrielLatencyBuckets = []float64{
	0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10,
}

var (
	gabrielInputsPublished = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "gabriel_producer_inputs_published_total",
		Help: "Inputs a producer published",
	}, []string{"producer_id"})

	gabrielInputsSent = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "gabriel_engine_inputs_sent_total",
		Help: "Inputs of a producer sent to an engine",
	}, []string{"producer_id", "engine_id"})

	gabrielOutcomes = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "gabriel_engine_outcomes_total",
		Help: "How offers of a producer's inputs to an engine ended",
	}, []string{"producer_id", "engine_id", "outcome"})

	gabrielInputLatency = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "gabriel_client_input_processing_latency_seconds",
		Help:    "From publishing an input to its result from an engine",
		Buckets: gabrielLatencyBuckets,
	}, []string{"producer_id", "engine_id"})

	gabrielEngineLatency = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "gabriel_engine_processing_latency_seconds",
		Help:    "From sending an input to an engine to its result",
		Buckets: gabrielLatencyBuckets,
	}, []string{"producer_id", "engine_id"})

	gabrielEngineWait = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "gabriel_engine_wait_seconds",
		Help:    "From the offer of an input to an engine to sending it",
		Buckets: gabrielLatencyBuckets,
	}, []string{"producer_id", "engine_id"})

	gabrielRemoteRoundTrip = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "gabriel_remote_round_trip_seconds",
		Help:    "Result latency of a remote engine, less the time on the remote server since the offer",
		Buckets: gabrielLatencyBuckets,
	}, []string{"producer_id", "engine_id"})

	gabrielDisconnects = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "gabriel_disconnects_total",
		Help: "Lost connections to a server of a producer's flow",
	}, []string{"producer_id"})

	gabrielEventsLost = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "gabriel_events_lost_total",
		Help: "Events about a producer's inputs that the vehicle missed",
	}, []string{"producer_id"})
)

// recentTimes remembers a time per key, and forgets it after
// gabrielMetricsWindow, for keys whose end never comes. Each time is stored
// with when it was seen on this machine, which decides when it is forgotten:
// a remote engine's times are on its own machine's clock.
type recentTimes[K comparable] struct {
	times    map[K]seenTime
	prunedAt gabriel.Timestamp
}

type seenTime struct {
	at, seen gabriel.Timestamp
}

func newRecentTimes[K comparable]() *recentTimes[K] {
	return &recentTimes[K]{times: make(map[K]seenTime)}
}

// put remembers at for key, as seen at seen on this machine.
func (r *recentTimes[K]) put(key K, at, seen gabriel.Timestamp) {
	r.times[key] = seenTime{at: at, seen: seen}
	if seen.Sub(r.prunedAt) < gabrielMetricsWindow {
		return
	}
	for k, t := range r.times {
		if seen.Sub(t.seen) >= gabrielMetricsWindow {
			delete(r.times, k)
		}
	}
	r.prunedAt = seen
}

func (r *recentTimes[K]) get(key K) (gabriel.Timestamp, bool) {
	t, ok := r.times[key]
	return t.at, ok
}

func (r *recentTimes[K]) take(key K) (gabriel.Timestamp, bool) {
	t, ok := r.times[key]
	delete(r.times, key)
	return t.at, ok
}

// publishTimes remembers when a producer published each input, by its
// sequence number, so that the latency of its results can be measured. The
// producer's goroutine writes it, and its subscription's goroutine reads it.
// It lives as long as the producer, whose session does not change, so the
// sequence number alone identifies an input.
type publishTimes struct {
	producer string
	mu       sync.Mutex
	times    *recentTimes[uint64]
}

func newPublishTimes(producer string) *publishTimes {
	return &publishTimes{producer: producer, times: newRecentTimes[uint64]()}
}

func (p *publishTimes) published(seq uint64, at gabriel.Timestamp) {
	gabrielInputsPublished.WithLabelValues(p.producer).Inc()
	p.mu.Lock()
	defer p.mu.Unlock()
	p.times.put(seq, at, at)
}

// publishedAt is when the input seq was published. An input has a result
// from each engine, so it is remembered until it is pruned.
func (p *publishTimes) publishedAt(seq uint64) (gabriel.Timestamp, bool) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.times.get(seq)
}

// offerKey identifies an offer of an input to an engine.
type offerKey struct {
	id     gabriel.InputID
	flow   string
	engine string
}

// gabrielMetrics records the metrics of one producer's inputs from their
// events. It is used by one goroutine, the subscription's.
type gabrielMetrics struct {
	published *publishTimes
	// sent is when each offer was sent, on the engine's machine.
	sent *recentTimes[offerKey]
	// timedOut is when each offer timed out, so that a result after it is
	// counted as late.
	timedOut *recentTimes[offerKey]
}

func newGabrielMetrics(published *publishTimes) *gabrielMetrics {
	return &gabrielMetrics{
		published: published,
		sent:      newRecentTimes[offerKey](),
		timedOut:  newRecentTimes[offerKey](),
	}
}

// record records one event about the producer's inputs.
func (m *gabrielMetrics) record(event gabriel.Event) {
	producer := m.published.producer
	key := offerKey{id: event.ID, flow: event.Flow, engine: event.Engine}
	// When the event reached this machine: a remote server's events are
	// stamped on its clock, and on arrival on this one.
	arrived := event.At
	if !event.ReceivedAt.IsZero() {
		arrived = event.ReceivedAt
	}
	switch event.Kind {
	case gabriel.EventSent:
		gabrielInputsSent.WithLabelValues(producer, event.Engine).Inc()
		if !event.OfferedAt.IsZero() {
			gabrielEngineWait.WithLabelValues(producer, event.Engine).
				Observe(event.At.Sub(event.OfferedAt).Seconds())
		}
		m.sent.put(key, event.At, arrived)
	case gabriel.EventResult:
		outcome := outcomeResult
		if _, late := m.timedOut.take(key); late {
			outcome = outcomeLateResult
		}
		gabrielOutcomes.WithLabelValues(producer, event.Engine, outcome).Inc()
		if sent, ok := m.sent.take(key); ok {
			gabrielEngineLatency.WithLabelValues(producer, event.Engine).
				Observe(event.At.Sub(sent).Seconds())
		}
		if published, ok := m.published.publishedAt(event.ID.Seq); ok {
			latency := arrived.Sub(published)
			gabrielInputLatency.WithLabelValues(producer, event.Engine).Observe(latency.Seconds())
			if !event.ReceivedAt.IsZero() && !event.OfferedAt.IsZero() {
				onServer := event.At.Sub(event.OfferedAt)
				gabrielRemoteRoundTrip.WithLabelValues(producer, event.Engine).
					Observe((latency - onServer).Seconds())
			}
		}
	case gabriel.EventSkipped:
		gabrielOutcomes.WithLabelValues(producer, event.Engine, outcomeSkipped).Inc()
	case gabriel.EventTimedOut:
		gabrielOutcomes.WithLabelValues(producer, event.Engine, outcomeTimedOut).Inc()
		m.timedOut.put(key, arrived, arrived)
	case gabriel.EventDisconnected:
		gabrielDisconnects.WithLabelValues(producer).Inc()
	case gabriel.EventLost:
		gabrielEventsLost.WithLabelValues(producer).Add(float64(event.Lost))
	}
}
