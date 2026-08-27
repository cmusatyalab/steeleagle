package main

import (
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// producerStats counts payloads sent by a single producer. Fields are
// updated concurrently by that producer's own send goroutine and read once,
// at shutdown, by printStats.
type producerStats struct {
	name  string
	sent  atomic.Uint64
	bytes atomic.Uint64
}

func (s *producerStats) record(size int) {
	s.sent.Add(1)
	s.bytes.Add(uint64(size))
}

// receivedStats counts results received from the server, broken down by the
// engine that produced them. The consumer callback only ever sees SUCCESS
// results (the vendored library handles other status codes itself and never
// forwards them), so this is inherently a count of successful deliveries,
// not a full success/error breakdown.
type receivedStats struct {
	mu       sync.Mutex
	total    uint64
	byEngine map[string]uint64
}

func (s *receivedStats) record(engineID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.total++
	if s.byEngine == nil {
		s.byEngine = make(map[string]uint64)
	}
	s.byEngine[engineID]++
}

// runConfig captures the resolved command-line flags a run was launched
// with, so printStats can report them alongside the stats they produced
// (flag defaults included, unlike a raw os.Args dump).
type runConfig struct {
	server                          string
	vehicleID, model                string
	telemetryEngines, frameEngines  string
	telemetryHz, frameHz            float64
	frameWidth, frameHeight         int
	frameQuality                    int
	duration                        time.Duration
	keepaliveTime, keepaliveTimeout time.Duration
	logLevel                        string
}

// printStats prints a human-readable summary of the run to stdout, separate
// from the structured zerolog output on stderr. Called on every shutdown
// path (graceful or forced) so a Ctrl-C or an exceeded -duration always
// leaves a report behind.
func printStats(cfg runConfig, startedAt time.Time, received *receivedStats, producers ...*producerStats) {
	elapsed := time.Since(startedAt)

	fmt.Println()
	fmt.Println("=== gabriel mock client stats ===")
	fmt.Println("config:")
	fmt.Printf("  server=%s vehicle-id=%s model=%s\n", cfg.server, cfg.vehicleID, cfg.model)
	fmt.Printf("  telemetry-engines=%s frame-engines=%s\n", cfg.telemetryEngines, cfg.frameEngines)
	fmt.Printf("  telemetry-hz=%g frame-hz=%g frame-width=%d frame-height=%d frame-quality=%d\n",
		cfg.telemetryHz, cfg.frameHz, cfg.frameWidth, cfg.frameHeight, cfg.frameQuality)
	fmt.Printf("  duration=%s keepalive-time=%s keepalive-timeout=%s log-level=%s\n",
		cfg.duration, cfg.keepaliveTime, cfg.keepaliveTimeout, cfg.logLevel)
	fmt.Printf("run duration: %s\n", elapsed.Round(time.Millisecond))
	fmt.Println("sent:")
	var totalBytes uint64
	for _, p := range producers {
		sent := p.sent.Load()
		bytes := p.bytes.Load()
		totalBytes += bytes
		var rate, avg, mbps float64
		if elapsed > 0 {
			rate = float64(sent) / elapsed.Seconds()
			mbps = float64(bytes) * 8 / elapsed.Seconds() / 1e6
		}
		if sent > 0 {
			avg = float64(bytes) / float64(sent)
		}
		fmt.Printf("  %-10s %6d payloads  %10d bytes total  %8.1f bytes avg  %6.1f/s  %7.3f Mbps\n", p.name, sent, bytes, avg, rate, mbps)
	}
	if elapsed > 0 {
		fmt.Printf("effective throughput: %.3f Mbps (%.1f Kbps)\n", float64(totalBytes)*8/elapsed.Seconds()/1e6, float64(totalBytes)*8/elapsed.Seconds()/1e3)
	}

	received.mu.Lock()
	defer received.mu.Unlock()
	fmt.Printf("received: %d results\n", received.total)
	for engineID, count := range received.byEngine {
		fmt.Printf("  %-10s %6d\n", engineID, count)
	}
	fmt.Println("==================================")
}
