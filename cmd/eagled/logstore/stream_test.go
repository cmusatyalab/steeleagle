package logstore

import (
	"context"
	"errors"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"
)

type collector struct {
	mu   sync.Mutex
	recs []Record
}

func (c *collector) emit(r Record) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.recs = append(c.recs, r)
	return nil
}

func (c *collector) snapshot() []Record {
	c.mu.Lock()
	defer c.mu.Unlock()
	return append([]Record(nil), c.recs...)
}

func (c *collector) waitFor(t *testing.T, n int) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if len(c.snapshot()) >= n {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for %d records, have %d", n, len(c.snapshot()))
}

func seqs(recs []Record) []uint64 {
	out := make([]uint64, len(recs))
	for i, r := range recs {
		out[i] = r.Seq
	}
	return out
}

func TestSubscribeFiltersBySource(t *testing.T) {
	s, _ := newTestStore(t, nil)
	sub := s.Subscribe([]string{"b"})
	defer sub.Close()
	s.Writer("a").Write([]byte("skip\n"))
	s.Writer("b").Write([]byte("keep\n"))
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	rec, err := sub.Next(ctx)
	if err != nil || rec.Source != "b" || rec.Text != "keep" {
		t.Fatalf("Next = %+v, %v", rec, err)
	}
}

func TestSlowSubscriberGetsGapMarkerAndNeverBlocksWriter(t *testing.T) {
	s, _ := newTestStore(t, func(o *Options) { o.SubscriberBuffer = 2 })
	sub := s.Subscribe(nil)
	defer sub.Close()
	w := s.Writer("daemon")
	done := make(chan struct{})
	go func() {
		for i := 0; i < 10; i++ {
			w.Write([]byte("line\n"))
		}
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("writer blocked on a subscriber that isn't reading")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	gap, err := sub.Next(ctx)
	if err != nil || gap.Dropped != 8 || gap.Seq != 0 || gap.Source != "daemon" || gap.Text == "" {
		t.Fatalf("gap marker = %+v, %v", gap, err)
	}
	for want := uint64(1); want <= 2; want++ {
		rec, err := sub.Next(ctx)
		if err != nil || rec.Seq != want {
			t.Fatalf("Next = %+v, %v, want seq %d", rec, err, want)
		}
	}
	// dropping is per-subscriber only: all 10 lines are still on disk
	if got := s.After("daemon", 0); len(got) != 10 {
		t.Fatalf("disk has %d records, want 10", len(got))
	}
}

func TestStreamBacklogThenLive(t *testing.T) {
	s, _ := newTestStore(t, nil)
	w := s.Writer("daemon")
	w.Write([]byte("a\nb\nc\n"))
	ctx, cancel := context.WithCancel(context.Background())
	c := &collector{}
	errc := make(chan error, 1)
	go func() { errc <- s.Stream(ctx, StreamOptions{Tail: 2, Follow: true}, c.emit) }()
	c.waitFor(t, 2)
	w.Write([]byte("d\ne\n"))
	c.waitFor(t, 4)
	cancel()
	if err := <-errc; !errors.Is(err, context.Canceled) {
		t.Fatalf("Stream returned %v, want context.Canceled", err)
	}
	if got := seqs(c.snapshot()); fmt.Sprint(got) != "[2 3 4 5]" {
		t.Fatalf("seqs = %v, want [2 3 4 5]", got)
	}
	s.subMu.Lock()
	defer s.subMu.Unlock()
	if len(s.subs) != 0 {
		t.Fatal("Stream must unsubscribe when it returns")
	}
}

func TestStreamAfterSeqTakesPrecedenceOverTail(t *testing.T) {
	s, _ := newTestStore(t, nil)
	s.Writer("daemon").Write([]byte("1\n2\n3\n4\n5\n"))
	c := &collector{}
	err := s.Stream(context.Background(), StreamOptions{Tail: 10, AfterSeq: map[string]uint64{"daemon": 3}}, c.emit)
	if err != nil {
		t.Fatal(err)
	}
	if got := seqs(c.snapshot()); fmt.Sprint(got) != "[4 5]" {
		t.Fatalf("seqs = %v, want [4 5]", got)
	}
}

func TestStreamHandoffHasNoGapOrDuplicate(t *testing.T) {
	s, _ := newTestStore(t, nil)
	w := s.Writer("daemon")
	started := make(chan struct{})
	go func() {
		for i := 1; i <= 500; i++ {
			w.Write([]byte("x\n"))
			if i == 50 {
				close(started)
			}
			time.Sleep(20 * time.Microsecond)
		}
	}()
	<-started
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	c := &collector{}
	go s.Stream(ctx, StreamOptions{Tail: 30, Follow: true}, c.emit)
	c.waitFor(t, 1)
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if recs := c.snapshot(); recs[len(recs)-1].Seq == 500 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	got := c.snapshot()
	for i := 1; i < len(got); i++ {
		if got[i].Seq != got[i-1].Seq+1 {
			t.Fatalf("gap or duplicate between seq %d and %d", got[i-1].Seq, got[i].Seq)
		}
	}
	if got[len(got)-1].Seq != 500 {
		t.Fatalf("never saw seq 500, last = %d", got[len(got)-1].Seq)
	}
}

func TestStreamMergesSourcesByTime(t *testing.T) {
	s, _ := newTestStore(t, nil)
	for i := 0; i < 3; i++ {
		s.Writer("a").Write([]byte("a\n"))
		time.Sleep(3 * time.Millisecond)
		s.Writer("b").Write([]byte("b\n"))
		time.Sleep(3 * time.Millisecond)
	}
	c := &collector{}
	if err := s.Stream(context.Background(), StreamOptions{Tail: 10}, c.emit); err != nil {
		t.Fatal(err)
	}
	got := c.snapshot()
	if len(got) != 6 {
		t.Fatalf("records = %d, want 6", len(got))
	}
	for i := 1; i < len(got); i++ {
		if got[i].Time.Before(got[i-1].Time) {
			t.Fatalf("records not ordered by time at %d", i)
		}
	}
}

func TestStreamAfterSeqCapsResumeBacklogWithGapMarker(t *testing.T) {
	s, _ := newTestStore(t, nil)
	w := s.Writer("daemon")
	total := MaxAfterSeqRecords + 10
	for i := 0; i < total; i++ {
		w.Write([]byte("line\n"))
	}
	c := &collector{}
	err := s.Stream(context.Background(), StreamOptions{AfterSeq: map[string]uint64{"daemon": 0}}, c.emit)
	if err != nil {
		t.Fatal(err)
	}
	got := c.snapshot()
	var gaps, real []Record
	for _, r := range got {
		if r.Dropped != 0 {
			gaps = append(gaps, r)
		} else {
			real = append(real, r)
		}
	}
	if len(gaps) != 1 {
		t.Fatalf("gap markers = %d, want 1: %+v", len(gaps), gaps)
	}
	wantCapped := uint64(total - MaxAfterSeqRecords)
	if gaps[0].Dropped != wantCapped || gaps[0].Seq != 0 || gaps[0].Source != "daemon" {
		t.Fatalf("gap marker = %+v, want Dropped=%d Seq=0 Source=daemon", gaps[0], wantCapped)
	}
	if len(real) != MaxAfterSeqRecords {
		t.Fatalf("real records = %d, want %d", len(real), MaxAfterSeqRecords)
	}
	if real[0].Seq != uint64(total-MaxAfterSeqRecords+1) || real[len(real)-1].Seq != uint64(total) {
		t.Fatalf("real records span seq %d..%d, want %d..%d", real[0].Seq, real[len(real)-1].Seq, total-MaxAfterSeqRecords+1, total)
	}
}

func TestStreamAfterSeqBelowRetentionEmitsGapMarker(t *testing.T) {
	s, dir := newTestStore(t, func(o *Options) { o.MaxFileBytes = 300; o.MaxFiles = 3 })
	w := s.Writer("daemon")
	for i := 1; i <= 40; i++ {
		w.Write([]byte(fmt.Sprintf("line-%02d padding padding\n", i)))
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 3 {
		t.Fatalf("files = %d, want 3 (setup should have rotated)", len(entries))
	}
	oldest := s.After("daemon", 0)[0].Seq
	if oldest <= 1 {
		t.Fatalf("oldest retained seq = %d, want > 1 so the cursor is below retention", oldest)
	}
	c := &collector{}
	err := s.Stream(context.Background(), StreamOptions{AfterSeq: map[string]uint64{"daemon": 0}}, c.emit)
	if err != nil {
		t.Fatal(err)
	}
	got := c.snapshot()
	var gaps int
	var gap Record
	for _, r := range got {
		if r.Dropped != 0 {
			gaps++
			gap = r
		}
	}
	if gaps != 1 {
		t.Fatalf("gap markers = %d, want exactly 1 in %+v", gaps, got)
	}
	if gap.Seq != 0 || gap.Source != "daemon" {
		t.Fatalf("gap marker = %+v, want Seq=0 Source=daemon", gap)
	}
	if want := oldest - 1; gap.Dropped != want {
		t.Fatalf("gap Dropped = %d, want %d (records already rotated out of retention)", gap.Dropped, want)
	}
}

func TestStreamStopsWhenEmitFails(t *testing.T) {
	s, _ := newTestStore(t, nil)
	s.Writer("daemon").Write([]byte("a\n"))
	boom := errors.New("client went away")
	err := s.Stream(context.Background(), StreamOptions{Tail: 5, Follow: true}, func(Record) error { return boom })
	if !errors.Is(err, boom) {
		t.Fatalf("Stream = %v, want emit's error", err)
	}
	s.subMu.Lock()
	defer s.subMu.Unlock()
	if len(s.subs) != 0 {
		t.Fatal("subscriber leaked after emit error")
	}
}
