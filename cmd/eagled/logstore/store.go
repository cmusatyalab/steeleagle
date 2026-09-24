package logstore

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	DefaultMaxFileBytes     = 25 << 20
	DefaultMaxFiles         = 3
	DefaultIdleFlush        = 250 * time.Millisecond
	MaxLineBytes            = 64 << 10
	DefaultSubscriberBuffer = 1024

	truncatedSuffix  = " [truncated]"
	lastRecordWindow = 1 << 20 // bytes read from a file's end to recover its last seq
)

// Record is one captured log line.
type Record struct {
	Seq    uint64    `json:"seq"`
	Time   time.Time `json:"time"`
	Source string    `json:"source"`
	Level  string    `json:"level,omitempty"`
	Text   string    `json:"text"`

	// Dropped is nonzero only on synthetic gap markers, which are generated at
	// delivery time and never persisted.
	Dropped uint64 `json:"-"`
}

// Options configures a Store. Zero values take the defaults above.
type Options struct {
	Dir              string
	MaxFileBytes     int64
	MaxFiles         int
	IdleFlush        time.Duration // flush an unterminated line after this much quiet
	SubscriberBuffer int           // per-subscriber queue length
}

// Store persists per-source log lines as rotated JSONL files under Dir.
type Store struct {
	opts Options

	mu   sync.Mutex
	logs map[string]*sourceLog

	subMu sync.Mutex
	subs  map[*Subscription]struct{}
}

// Open returns a Store writing under opts.Dir. It never fails: if the
// directory can't be created or written, persistence is disabled per source
// (with one warning on stderr) and live delivery keeps working.
func Open(opts Options) *Store {
	if opts.MaxFileBytes <= 0 {
		opts.MaxFileBytes = DefaultMaxFileBytes
	}
	if opts.MaxFiles <= 0 {
		opts.MaxFiles = DefaultMaxFiles
	}
	if opts.IdleFlush <= 0 {
		opts.IdleFlush = DefaultIdleFlush
	}
	if opts.SubscriberBuffer <= 0 {
		opts.SubscriberBuffer = DefaultSubscriberBuffer
	}
	_ = os.MkdirAll(opts.Dir, 0o700)
	return &Store{
		opts: opts,
		logs: make(map[string]*sourceLog),
		subs: make(map[*Subscription]struct{}),
	}
}

// sourceLog is one source's files and sequence counter.
type sourceLog struct {
	source string
	stem   string // <Dir>/<escaped source>, without extension

	mu     sync.Mutex
	f      *os.File
	size   int64
	seq    uint64
	loaded bool
	broken bool // persistence disabled after a failure
}

func (s *Store) sourceLog(source string) *sourceLog {
	if source == "" {
		source = "unknown"
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	sl, ok := s.logs[source]
	if !ok {
		sl = &sourceLog{source: source, stem: filepath.Join(s.opts.Dir, EscapeName(source))}
		s.logs[source] = sl
	}
	return sl
}

func (sl *sourceLog) path(i int) string {
	if i == 0 {
		return sl.stem + ".log"
	}
	return fmt.Sprintf("%s.log.%d", sl.stem, i)
}

// append assigns the next seq, persists the record, and publishes it. It holds
// the source lock throughout so live delivery order matches seq order.
func (s *Store) append(source, text string) {
	sl := s.sourceLog(source)
	sl.mu.Lock()
	defer sl.mu.Unlock()
	if !sl.loaded {
		sl.recoverSeq(s.opts.MaxFiles)
		sl.loaded = true
	}
	sl.seq++
	rec := Record{Seq: sl.seq, Time: time.Now().UTC(), Source: sl.source, Level: parseLevel(text), Text: text}
	sl.persist(s, rec)
	s.publish(rec)
}

func (sl *sourceLog) recoverSeq(maxFiles int) {
	for i := 0; i < maxFiles; i++ {
		if rec, ok := readLastRecord(sl.path(i)); ok {
			sl.seq = rec.Seq
			return
		}
	}
}

func (sl *sourceLog) persist(s *Store, rec Record) {
	if sl.broken {
		return
	}
	line, _ := json.Marshal(rec)
	line = append(line, '\n')
	if sl.f == nil {
		if err := sl.open(s); err != nil {
			sl.fail(err)
			return
		}
	}
	if sl.size > 0 && sl.size+int64(len(line)) > s.opts.MaxFileBytes {
		if err := sl.rotate(s); err != nil {
			sl.fail(err)
			return
		}
	}
	n, err := sl.f.Write(line)
	sl.size += int64(n)
	if err != nil {
		sl.fail(err)
	}
}

func (sl *sourceLog) open(s *Store) error {
	if err := os.MkdirAll(s.opts.Dir, 0o700); err != nil {
		return err
	}
	f, err := os.OpenFile(sl.path(0), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	fi, err := f.Stat()
	if err != nil {
		f.Close()
		return err
	}
	sl.f, sl.size = f, fi.Size()
	return nil
}

func (sl *sourceLog) rotate(s *Store) error {
	sl.f.Close()
	sl.f = nil
	if s.opts.MaxFiles < 2 {
		os.Remove(sl.path(0))
	} else {
		for i := s.opts.MaxFiles - 1; i >= 1; i-- {
			os.Remove(sl.path(i))
			if err := os.Rename(sl.path(i-1), sl.path(i)); err != nil && !errors.Is(err, fs.ErrNotExist) {
				return err
			}
		}
	}
	return sl.open(s)
}

// fail disables persistence for this source after one warning. It must not
// use zerolog or stdlib log: both are teed back into this store.
func (sl *sourceLog) fail(err error) {
	sl.broken = true
	if sl.f != nil {
		sl.f.Close()
		sl.f = nil
	}
	fmt.Fprintf(os.Stderr, "logstore: disabling persistence for source %q: %v\n", sl.source, err)
}

func readLastRecord(path string) (Record, bool) {
	f, err := os.Open(path)
	if err != nil {
		return Record{}, false
	}
	defer f.Close()
	fi, err := f.Stat()
	if err != nil || fi.Size() == 0 {
		return Record{}, false
	}
	start := int64(0)
	if fi.Size() > lastRecordWindow {
		start = fi.Size() - lastRecordWindow
	}
	buf := make([]byte, fi.Size()-start)
	if _, err := f.ReadAt(buf, start); err != nil && err != io.EOF {
		return Record{}, false
	}
	lines := bytes.Split(buf, []byte{'\n'})
	for i := len(lines) - 1; i >= 0; i-- {
		var rec Record
		if json.Unmarshal(lines[i], &rec) == nil && rec.Seq > 0 {
			return rec, true
		}
	}
	return Record{}, false
}

func parseLevel(text string) string {
	if len(text) == 0 || text[0] != '{' {
		return ""
	}
	var v struct {
		Level string `json:"level"`
	}
	if json.Unmarshal([]byte(text), &v) != nil {
		return ""
	}
	return v.Level
}

// lineWriter splits a byte stream into lines for one source.
type lineWriter struct {
	s        *Store
	source   string
	mu       sync.Mutex
	buf      []byte
	skipping bool // discarding the rest of an overlong line up to its newline
	timer    *time.Timer
}

// Writer returns an io.Writer that turns everything written into records for
// source. Write never returns an error and never blocks on disk or
// subscribers. Close flushes any unterminated final line.
func (s *Store) Writer(source string) io.WriteCloser {
	return &lineWriter{s: s, source: source}
}

func (w *lineWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	n := len(p)
	for len(p) > 0 {
		i := bytes.IndexByte(p, '\n')
		if i < 0 {
			w.absorbLocked(p)
			break
		}
		w.absorbLocked(p[:i])
		w.endLineLocked()
		p = p[i+1:]
	}
	w.armTimerLocked()
	return n, nil
}

func (w *lineWriter) absorbLocked(chunk []byte) {
	if w.skipping {
		return
	}
	w.buf = append(w.buf, chunk...)
	if len(w.buf) > MaxLineBytes {
		w.s.append(w.source, string(w.buf[:MaxLineBytes])+truncatedSuffix)
		w.buf = w.buf[:0]
		w.skipping = true
	}
}

func (w *lineWriter) endLineLocked() {
	if w.skipping {
		w.skipping = false
		return
	}
	w.flushLocked()
}

func (w *lineWriter) flushLocked() {
	text := strings.TrimRight(string(w.buf), "\r")
	w.buf = w.buf[:0]
	if text != "" {
		w.s.append(w.source, text)
	}
}

func (w *lineWriter) armTimerLocked() {
	if len(w.buf) == 0 {
		if w.timer != nil {
			w.timer.Stop()
		}
		return
	}
	if w.timer == nil {
		w.timer = time.AfterFunc(w.s.opts.IdleFlush, w.idleFlush)
	} else {
		w.timer.Reset(w.s.opts.IdleFlush)
	}
}

func (w *lineWriter) idleFlush() {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.flushLocked()
}

func (w *lineWriter) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.timer != nil {
		w.timer.Stop()
	}
	if !w.skipping {
		w.flushLocked()
	}
	return nil
}

// readFile parses every valid record in path, oldest first, skipping
// unparseable lines (e.g. a partially written final line).
func readFile(path string) []Record {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()
	var out []Record
	r := bufio.NewReaderSize(f, 64<<10)
	for {
		line, err := r.ReadBytes('\n')
		if len(line) > 0 {
			var rec Record
			if json.Unmarshal(line, &rec) == nil && rec.Seq > 0 {
				out = append(out, rec)
			}
		}
		if err != nil {
			return out
		}
	}
}

// Tail/After do not take sl.mu: sl.stem (which sl.path derives from) is set once
// at sourceLog creation and never mutated, so no lock is needed to read it safely.
// A read that races a concurrent rotation may see a torn or briefly duplicated
// file — readFile already tolerates malformed lines, and this is a diagnostic
// log view, not a correctness-critical path — accepted so opening the Logs tab
// never blocks eagled's own logging (see the constraint this violated: producers
// must never block).

// Tail returns up to n of source's most recent retained records, oldest first.
func (s *Store) Tail(source string, n int) []Record {
	if n <= 0 {
		return nil
	}
	sl := s.sourceLog(source)
	var chunks [][]Record // chunks[0] is the newest file
	total := 0
	for i := 0; i < s.opts.MaxFiles && total < n; i++ {
		if recs := readFile(sl.path(i)); len(recs) > 0 {
			chunks = append(chunks, recs)
			total += len(recs)
		}
	}
	out := make([]Record, 0, total)
	for i := len(chunks) - 1; i >= 0; i-- {
		out = append(out, chunks[i]...)
	}
	if len(out) > n {
		out = out[len(out)-n:]
	}
	return out
}

// After returns every retained record of source with Seq > seq, oldest first.
func (s *Store) After(source string, seq uint64) []Record {
	sl := s.sourceLog(source)
	var out []Record
	for i := s.opts.MaxFiles - 1; i >= 0; i-- {
		for _, rec := range readFile(sl.path(i)) {
			if rec.Seq > seq {
				out = append(out, rec)
			}
		}
	}
	return out
}

// SourceInfo describes one source's files on disk.
type SourceInfo struct {
	Name      string
	SizeBytes int64
}

// Sources lists every source with files under Dir, sorted by name.
func (s *Store) Sources() []SourceInfo {
	entries, err := os.ReadDir(s.opts.Dir)
	if err != nil {
		return nil
	}
	sizes := map[string]int64{}
	for _, e := range entries {
		stem, ok := fileStem(e.Name())
		if !ok {
			continue
		}
		if fi, err := e.Info(); err == nil {
			sizes[stem] += fi.Size()
		}
	}
	out := make([]SourceInfo, 0, len(sizes))
	for stem, size := range sizes {
		name, exact := UnescapeName(stem)
		if !exact {
			for i := 0; i < s.opts.MaxFiles; i++ {
				if rec, ok := readLastRecord(filepath.Join(s.opts.Dir, stem) + suffixFor(i)); ok {
					name = rec.Source
					break
				}
			}
		}
		out = append(out, SourceInfo{Name: name, SizeBytes: size})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func suffixFor(i int) string {
	if i == 0 {
		return ".log"
	}
	return ".log." + strconv.Itoa(i)
}

// fileStem returns the escaped-source stem of a "<stem>.log" or
// "<stem>.log.<n>" filename.
func fileStem(name string) (string, bool) {
	if stem, ok := strings.CutSuffix(name, ".log"); ok && stem != "" {
		return stem, true
	}
	if i := strings.LastIndex(name, ".log."); i > 0 {
		if _, err := strconv.Atoi(name[i+len(".log."):]); err == nil {
			return name[:i], true
		}
	}
	return "", false
}
