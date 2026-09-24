package logstore

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func newTestStore(t *testing.T, mod func(*Options)) (*Store, string) {
	t.Helper()
	dir := filepath.Join(t.TempDir(), "logs")
	opts := Options{Dir: dir, IdleFlush: 20 * time.Millisecond}
	if mod != nil {
		mod(&opts)
	}
	return Open(opts), dir
}

func texts(recs []Record) []string {
	out := make([]string, len(recs))
	for i, r := range recs {
		out[i] = r.Text
	}
	return out
}

func TestWriterSplitsLinesAcrossWrites(t *testing.T) {
	s, _ := newTestStore(t, nil)
	w := s.Writer("daemon")
	for _, chunk := range []string{"hello\nwor", "ld\r\n", "\n", "x\n"} {
		n, err := w.Write([]byte(chunk))
		if n != len(chunk) || err != nil {
			t.Fatalf("Write(%q) = (%d, %v)", chunk, n, err)
		}
	}
	got := s.Tail("daemon", 10)
	if want := []string{"hello", "world", "x"}; fmt.Sprint(texts(got)) != fmt.Sprint(want) {
		t.Fatalf("texts = %v, want %v (blank lines are skipped)", texts(got), want)
	}
	for i, r := range got {
		if r.Seq != uint64(i+1) || r.Source != "daemon" || r.Time.IsZero() {
			t.Errorf("record %d = %+v", i, r)
		}
	}
}

func TestLevelParsedOnlyFromZerologJSON(t *testing.T) {
	s, _ := newTestStore(t, nil)
	w := s.Writer("daemon")
	w.Write([]byte(`{"level":"warn","message":"x"}` + "\nplain text\n{not json\n"))
	got := s.Tail("daemon", 10)
	if got[0].Level != "warn" || got[1].Level != "" || got[2].Level != "" {
		t.Fatalf("levels = %q %q %q", got[0].Level, got[1].Level, got[2].Level)
	}
}

func TestSeqAndHistorySurviveReopen(t *testing.T) {
	s, dir := newTestStore(t, nil)
	w := s.Writer("daemon")
	w.Write([]byte("a\nb\nc\n"))

	s2 := Open(Options{Dir: dir})
	s2.Writer("daemon").Write([]byte("d\n"))
	got := s2.Tail("daemon", 10)
	if want := []string{"a", "b", "c", "d"}; fmt.Sprint(texts(got)) != fmt.Sprint(want) {
		t.Fatalf("texts = %v, want %v", texts(got), want)
	}
	if got[3].Seq != 4 {
		t.Fatalf("seq after reopen = %d, want 4", got[3].Seq)
	}
}

func TestRotationKeepsBoundedFilesAndMonotonicSeq(t *testing.T) {
	s, dir := newTestStore(t, func(o *Options) { o.MaxFileBytes = 300; o.MaxFiles = 3 })
	w := s.Writer("daemon")
	for i := 1; i <= 40; i++ {
		w.Write([]byte(fmt.Sprintf("line-%02d padding padding\n", i)))
	}
	entries, _ := os.ReadDir(dir)
	var names []string
	for _, e := range entries {
		names = append(names, e.Name())
	}
	if len(names) != 3 {
		t.Fatalf("files = %v, want exactly .log, .log.1, .log.2", names)
	}
	all := s.After("daemon", 0)
	if all[len(all)-1].Seq != 40 {
		t.Fatalf("last seq = %d, want 40", all[len(all)-1].Seq)
	}
	if all[0].Seq == 1 {
		t.Fatal("oldest lines should have rotated out")
	}
	for i := 1; i < len(all); i++ {
		if all[i].Seq != all[i-1].Seq+1 {
			t.Fatalf("seq gap between %d and %d", all[i-1].Seq, all[i].Seq)
		}
	}
	tail := s.Tail("daemon", 5)
	if len(tail) != 5 || tail[4].Seq != 40 {
		t.Fatalf("Tail(5) = %+v", tail)
	}
}

func TestOverlongLineIsTruncatedAndNextLineIsIntact(t *testing.T) {
	s, _ := newTestStore(t, nil)
	w := s.Writer("daemon")
	w.Write([]byte(strings.Repeat("x", 3*MaxLineBytes) + "\nnext\n"))
	got := s.Tail("daemon", 10)
	if len(got) != 2 || got[1].Text != "next" {
		t.Fatalf("records = %d, second = %q", len(got), got[len(got)-1].Text)
	}
	if len(got[0].Text) > MaxLineBytes+len(" [truncated]") || !strings.HasSuffix(got[0].Text, " [truncated]") {
		t.Fatalf("first record len %d, suffix ok=%v", len(got[0].Text), strings.HasSuffix(got[0].Text, " [truncated]"))
	}
}

func TestIdleFlushEmitsUnterminatedLine(t *testing.T) {
	s, _ := newTestStore(t, nil)
	s.Writer("daemon").Write([]byte("partial"))
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if got := s.Tail("daemon", 1); len(got) == 1 && got[0].Text == "partial" {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("unterminated line was never flushed")
}

func TestCloseFlushesPartialLine(t *testing.T) {
	s, _ := newTestStore(t, func(o *Options) { o.IdleFlush = time.Hour })
	w := s.Writer("daemon")
	w.Write([]byte("tail-without-newline"))
	w.Close()
	if got := s.Tail("daemon", 1); len(got) != 1 || got[0].Text != "tail-without-newline" {
		t.Fatalf("got %+v", got)
	}
}

func TestUnwritableDirNeverFailsTheProducer(t *testing.T) {
	blocker := filepath.Join(t.TempDir(), "file")
	os.WriteFile(blocker, []byte("x"), 0o644)
	s := Open(Options{Dir: filepath.Join(blocker, "logs")}) // MkdirAll must fail
	w := s.Writer("daemon")
	n, err := w.Write([]byte("still fine\n"))
	if n != len("still fine\n") || err != nil {
		t.Fatalf("Write = (%d, %v)", n, err)
	}
	if got := s.Tail("daemon", 10); len(got) != 0 {
		t.Fatalf("nothing should be persisted, got %+v", got)
	}
}

func TestSourcesUseReadableFilenamesAndTrueNames(t *testing.T) {
	s, dir := newTestStore(t, nil)
	long := strings.Repeat("x", 300)
	for _, src := range []string{"daemon", "a b", long} {
		s.Writer(src).Write([]byte("hi\n"))
	}
	if _, err := os.Stat(filepath.Join(dir, "a%20b.log")); err != nil {
		t.Fatalf("expected readable escaped filename a%%20b.log: %v", err)
	}
	var names []string
	for _, si := range s.Sources() {
		if si.SizeBytes <= 0 {
			t.Errorf("source %q has size %d", si.Name, si.SizeBytes)
		}
		names = append(names, si.Name)
	}
	want := []string{"a b", "daemon", long}
	if fmt.Sprint(names) != fmt.Sprint(want) {
		t.Fatalf("Sources = %v, want %v", names, want)
	}
}

func TestConcurrentWritersKeepSeqUniqueAndOrdered(t *testing.T) {
	s, _ := newTestStore(t, nil)
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			w := s.Writer("daemon")
			for i := 0; i < 100; i++ {
				w.Write([]byte("line\n"))
			}
		}()
	}
	wg.Wait()
	all := s.After("daemon", 0)
	if len(all) != 800 {
		t.Fatalf("records = %d, want 800", len(all))
	}
	for i, r := range all {
		if r.Seq != uint64(i+1) {
			t.Fatalf("record %d has seq %d", i, r.Seq)
		}
	}
}
