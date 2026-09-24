package logstore

import (
	"context"
	"fmt"
	"sort"
	"sync"
	"time"
)

// Subscription receives live records from a Store. Its queue is bounded:
// when it is full, new records are dropped for this subscriber only (disk is
// unaffected) and reported later as a gap marker.
type Subscription struct {
	s       *Store
	sources map[string]struct{} // nil = all sources
	ch      chan Record

	mu      sync.Mutex
	dropped map[string]uint64
}

// Subscribe registers a live subscriber for sources (nil or empty = all).
func (s *Store) Subscribe(sources []string) *Subscription {
	sub := &Subscription{
		s:       s,
		ch:      make(chan Record, s.opts.SubscriberBuffer),
		dropped: make(map[string]uint64),
	}
	if len(sources) > 0 {
		sub.sources = make(map[string]struct{}, len(sources))
		for _, src := range sources {
			sub.sources[src] = struct{}{}
		}
	}
	s.subMu.Lock()
	s.subs[sub] = struct{}{}
	s.subMu.Unlock()
	return sub
}

// Close unregisters the subscriber. Safe to call more than once.
func (sub *Subscription) Close() {
	sub.s.subMu.Lock()
	delete(sub.s.subs, sub)
	sub.s.subMu.Unlock()
}

// publish delivers rec to every matching subscriber without ever blocking.
// Callers hold the record's source lock, so per-source order is preserved.
func (s *Store) publish(rec Record) {
	s.subMu.Lock()
	defer s.subMu.Unlock()
	for sub := range s.subs {
		if sub.sources != nil {
			if _, ok := sub.sources[rec.Source]; !ok {
				continue
			}
		}
		select {
		case sub.ch <- rec:
		default:
			sub.mu.Lock()
			sub.dropped[rec.Source]++
			sub.mu.Unlock()
		}
	}
}

// Next returns the next record, or a pending gap marker first if records were
// dropped. It blocks until one is available or ctx is done.
func (sub *Subscription) Next(ctx context.Context) (Record, error) {
	if gap, ok := sub.takeGap(); ok {
		return gap, nil
	}
	select {
	case rec := <-sub.ch:
		return rec, nil
	case <-ctx.Done():
		return Record{}, ctx.Err()
	}
}

func (sub *Subscription) takeGap() (Record, bool) {
	sub.mu.Lock()
	defer sub.mu.Unlock()
	if len(sub.dropped) == 0 {
		return Record{}, false
	}
	names := make([]string, 0, len(sub.dropped))
	for name := range sub.dropped {
		names = append(names, name)
	}
	sort.Strings(names)
	name := names[0]
	n := sub.dropped[name]
	delete(sub.dropped, name)
	return Record{
		Source:  name,
		Dropped: n,
		Time:    time.Now().UTC(),
		Text:    fmt.Sprintf("%d log lines dropped (slow consumer)", n),
	}, true
}

// MaxAfterSeqRecords caps how many records a single resume (After) delivers per
// source, mirroring the frontend's own row cap (logState.js's MAX_RECORDS) --
// there is no point returning more than the client will ever keep, and an
// unbounded resume after a long partition is a real memory/bandwidth risk.
const MaxAfterSeqRecords = 5000

// StreamOptions selects what Stream sends.
type StreamOptions struct {
	Sources  []string          // empty = every source on disk (and, with Follow, any new one)
	Tail     int               // backlog records per source when there is no cursor; 0 = none
	Follow   bool              // keep streaming live records after the backlog
	AfterSeq map[string]uint64 // per-source resume cursor; overrides Tail for that source
}

// Stream emits the requested backlog merged by time, then (with Follow) live
// records until ctx is canceled. It subscribes before reading the backlog and
// dedupes by per-source seq, so there is no gap or duplicate at the handoff.
func (s *Store) Stream(ctx context.Context, opts StreamOptions, emit func(Record) error) error {
	var sub *Subscription
	if opts.Follow {
		sub = s.Subscribe(opts.Sources)
		defer sub.Close()
	}
	sources := opts.Sources
	if len(sources) == 0 {
		for _, si := range s.Sources() {
			sources = append(sources, si.Name)
		}
	}

	sent := map[string]uint64{}
	var backlog []Record
	for _, src := range sources {
		if cur, ok := opts.AfterSeq[src]; ok {
			sent[src] = cur
			recs := s.After(src, cur)
			if len(recs) > 0 && recs[0].Seq > cur+1 {
				gap := recs[0].Seq - cur - 1
				backlog = append(backlog, Record{
					Source: src, Dropped: gap, Time: time.Now().UTC(),
					Text: fmt.Sprintf("%d log lines dropped (rotated out of retention)", gap),
				})
			}
			if len(recs) > MaxAfterSeqRecords {
				capped := uint64(len(recs) - MaxAfterSeqRecords)
				recs = recs[len(recs)-MaxAfterSeqRecords:]
				backlog = append(backlog, Record{
					Source: src, Dropped: capped, Time: time.Now().UTC(),
					Text: fmt.Sprintf("%d log lines dropped (resume backlog capped)", capped),
				})
			}
			backlog = append(backlog, recs...)
		} else if opts.Tail > 0 {
			backlog = append(backlog, s.Tail(src, opts.Tail)...)
		}
	}
	sort.SliceStable(backlog, func(i, j int) bool {
		a, b := backlog[i], backlog[j]
		if !a.Time.Equal(b.Time) {
			return a.Time.Before(b.Time)
		}
		if a.Source != b.Source {
			return a.Source < b.Source
		}
		return a.Seq < b.Seq
	})
	for _, rec := range backlog {
		if err := emit(rec); err != nil {
			return err
		}
		if rec.Seq > sent[rec.Source] {
			sent[rec.Source] = rec.Seq
		}
	}
	if !opts.Follow {
		return nil
	}

	for {
		rec, err := sub.Next(ctx)
		if err != nil {
			return err
		}
		if rec.Dropped == 0 {
			if rec.Seq <= sent[rec.Source] {
				continue
			}
			sent[rec.Source] = rec.Seq
		}
		if err := emit(rec); err != nil {
			return err
		}
	}
}
