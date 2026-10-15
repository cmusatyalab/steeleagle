package vehicle

// A record of every input and event of a vehicle's Gabriel flow, for
// analysis after a flight. It is written in gabriel-bench's format, so that
// bench/analyze.py in Gabriel reads a flight as it reads a bench run. Each
// start of the flow writes a directory of its own, named after the time it
// started:
//
//   - inputs.csv: one row per published input.
//   - events.csv: one row per event about an input.
//   - run.toml: the flow, the remote server, and when the recording started.
//
// Times are nanoseconds on this machine's monotonic clock, except that a
// remote server's events are stamped on its own clock (at_ns, offered_ns)
// and on this one when they arrive (received_ns). run.toml gives the wall
// clock time of started_ns, to line the rows up with telemetry.
//
// The files are plain CSV, flushed every gabrielRecordFlushInterval, so that
// a crash or a power cut loses at most that much. A flow with 30 fps frames,
// 10 Hz telemetry and one engine writes about 50 MB an hour. A recording
// stops at gabrielRecordMaxBytes, so that it cannot fill the disk.

import (
	"bytes"
	"encoding/csv"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"time"

	"github.com/BurntSushi/toml"
	gabriel "github.com/cmusatyalab/gabriel/go"
	"github.com/rs/zerolog"
)

const (
	gabrielInputsFile = "inputs.csv"
	gabrielEventsFile = "events.csv"
	gabrielRunFile    = "run.toml"
	// gabrielRecordFlushInterval bounds how much of a recording a crash
	// loses.
	gabrielRecordFlushInterval = time.Second
	// gabrielRecordMaxBytes is where a recording stops: about 2.5 hours of
	// the flow above, beyond any flight. Each start of the flow records
	// anew, and old recordings are kept, so clear them out now and then.
	gabrielRecordMaxBytes = 128 << 20
	// gabrielRecordDirLayout names a recording's directory after when it
	// started, in UTC, so that the directories sort in time order.
	gabrielRecordDirLayout = "20060102T150405Z"
	gabrielRecordDirPerm   = 0o755
	gabrielRecordFilePerm  = 0o644
)

var (
	gabrielInputsHeader = []string{"producer", "session", "seq", "published_ns"}
	gabrielEventsHeader = []string{
		"kind", "producer", "session", "seq", "flow", "engine", "forward",
		"result_len", "offered_ns", "at_ns", "received_ns", "lost",
	}
	// gabrielEventKindNames and gabrielForwardNames are the names
	// gabriel-bench writes, which analyze.py expects.
	gabrielEventKindNames = map[gabriel.EventKind]string{
		gabriel.EventAccepted:     "Accepted",
		gabriel.EventSent:         "Sent",
		gabriel.EventResult:       "Result",
		gabriel.EventSkipped:      "Skipped",
		gabriel.EventTimedOut:     "TimedOut",
		gabriel.EventDisconnected: "Disconnected",
		gabriel.EventDerived:      "Derived",
		gabriel.EventLost:         "Lost",
	}
	gabrielForwardNames = map[gabriel.Forward]string{
		gabriel.ForwardStop: "Stop",
		gabriel.ForwardPass: "Pass",
		gabriel.ForwardEmit: "Emit",
	}
)

// gabrielRun is run.toml: what analyze.py reads of a bench run's spec, and
// when the recording started.
type gabrielRun struct {
	Flow GabrielFlow `toml:"flow"`
	// Remote is set when the flow has a remote server, which has a clock of
	// its own.
	Remote    *gabrielRunRemote   `toml:"remote,omitempty"`
	Recording gabrielRunRecording `toml:"recording"`
}

type gabrielRunRemote struct {
	Addr string `toml:"addr"`
}

type gabrielRunRecording struct {
	Vehicle string `toml:"vehicle"`
	// StartedAt is the wall clock time at StartedNs.
	StartedAt time.Time `toml:"started_at"`
	StartedNs uint64    `toml:"started_ns"`
}

// gabrielRecorder writes a recording. Its producers and subscriptions write
// to it from their own goroutines. A nil recorder records nothing.
type gabrielRecorder struct {
	mu        sync.Mutex
	dir       string
	files     []*os.File
	inputs    *csv.Writer
	events    *csv.Writer
	written   *countingWriter
	flushedAt time.Time
	full      bool
	log       zerolog.Logger
}

// countingWriter counts the bytes written through it.
type countingWriter struct {
	n int64
}

func (c *countingWriter) Write(p []byte) (int, error) {
	c.n += int64(len(p))
	return len(p), nil
}

// newGabrielRecorder starts a recording of the vehicle's flow, which has
// the remote server remote ("" if none), in a new directory in dir.
func newGabrielRecorder(
	dir, vehicle string,
	flow GabrielFlow,
	remote string,
	log zerolog.Logger,
) (_ *gabrielRecorder, err error) {
	startedNs, startedAt := gabriel.Now(), time.Now().UTC()
	dir = filepath.Join(dir, startedAt.Format(gabrielRecordDirLayout))
	if err := os.MkdirAll(dir, gabrielRecordDirPerm); err != nil {
		return nil, fmt.Errorf("creating the gabriel recording directory: %w", err)
	}

	run := gabrielRun{
		Flow: flow,
		Recording: gabrielRunRecording{
			Vehicle:   vehicle,
			StartedAt: startedAt,
			StartedNs: uint64(startedNs),
		},
	}
	if remote != "" {
		run.Remote = &gabrielRunRemote{Addr: remote}
	}
	var runToml bytes.Buffer
	if err := toml.NewEncoder(&runToml).Encode(run); err != nil {
		return nil, fmt.Errorf("encoding %s: %w", gabrielRunFile, err)
	}
	if err := os.WriteFile(filepath.Join(dir, gabrielRunFile), runToml.Bytes(), gabrielRecordFilePerm); err != nil {
		return nil, fmt.Errorf("writing %s: %w", gabrielRunFile, err)
	}

	r := &gabrielRecorder{
		dir:       dir,
		written:   &countingWriter{},
		flushedAt: time.Now(),
		log:       log.With().Str("recording", dir).Logger(),
	}
	defer func() {
		if err != nil {
			r.closeFiles()
		}
	}()
	if r.inputs, err = r.create(gabrielInputsFile, gabrielInputsHeader); err != nil {
		return nil, err
	}
	if r.events, err = r.create(gabrielEventsFile, gabrielEventsHeader); err != nil {
		return nil, err
	}
	r.log.Info().Msg("recording the gabriel flow")
	return r, nil
}

// create creates the CSV file name in the recording's directory, and writes
// its header.
func (r *gabrielRecorder) create(name string, header []string) (*csv.Writer, error) {
	f, err := os.OpenFile(filepath.Join(r.dir, name), os.O_WRONLY|os.O_CREATE|os.O_EXCL, gabrielRecordFilePerm)
	if err != nil {
		return nil, fmt.Errorf("creating %s: %w", name, err)
	}
	r.files = append(r.files, f)
	w := csv.NewWriter(io.MultiWriter(f, r.written))
	if err := w.Write(header); err != nil {
		return nil, fmt.Errorf("writing %s: %w", name, err)
	}
	return w, nil
}

// input records that the producer published the input seq at publishedAt.
func (r *gabrielRecorder) input(producer string, session, seq uint64, publishedAt gabriel.Timestamp) {
	if r == nil {
		return
	}
	r.write(r.inputs, []string{producer, uintField(session), uintField(seq), uintField(uint64(publishedAt))})
}

// event records an event about the inputs of producer.
func (r *gabrielRecorder) event(producer string, event gabriel.Event) {
	if r == nil {
		return
	}
	kind, ok := gabrielEventKindNames[event.Kind]
	if !ok {
		kind = event.Kind.String()
	}
	row := []string{kind, producer, "", "", event.Flow, event.Engine, "", "", "", "", "", ""}
	const (
		session, seq, forward, resultLen, offered, at, received, lost = 2, 3, 6, 7, 8, 9, 10, 11
	)
	switch event.Kind {
	case gabriel.EventLost:
		row[lost] = uintField(event.Lost)
		r.write(r.events, row)
		return
	case gabriel.EventDisconnected:
	default:
		row[session], row[seq] = uintField(event.ID.Session), uintField(event.ID.Seq)
	}
	if event.Kind == gabriel.EventResult {
		row[forward] = gabrielForwardNames[event.Forward]
		row[resultLen] = strconv.Itoa(len(event.Result))
	}
	row[offered] = timestampField(event.OfferedAt)
	row[at] = timestampField(event.At)
	row[received] = timestampField(event.ReceivedAt)
	r.write(r.events, row)
}

// write writes a row, and flushes the recording if it is due. Rows past
// gabrielRecordMaxBytes are dropped.
func (r *gabrielRecorder) write(w *csv.Writer, row []string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.full {
		return
	}
	if err := w.Write(row); err != nil {
		r.log.Err(err).Msg("writing the gabriel recording")
		return
	}
	if time.Since(r.flushedAt) >= gabrielRecordFlushInterval {
		r.flush()
	}
	if r.written.n >= gabrielRecordMaxBytes {
		r.full = true
		r.log.Warn().Int("max-bytes", gabrielRecordMaxBytes).
			Msg("the gabriel recording is full; recording no more")
	}
}

// flush writes the buffered rows to the files. The caller holds r.mu.
func (r *gabrielRecorder) flush() {
	for _, w := range []*csv.Writer{r.inputs, r.events} {
		w.Flush()
		if err := w.Error(); err != nil {
			r.log.Err(err).Msg("writing the gabriel recording")
		}
	}
	r.flushedAt = time.Now()
}

// close flushes the recording and closes its files.
func (r *gabrielRecorder) close() {
	if r == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.flush()
	r.closeFiles()
}

func (r *gabrielRecorder) closeFiles() {
	for _, f := range r.files {
		if err := f.Close(); err != nil {
			r.log.Err(err).Msg("closing the gabriel recording")
		}
	}
	r.files = nil
}

func uintField(v uint64) string {
	return strconv.FormatUint(v, 10)
}

// timestampField is t in nanoseconds, or empty if t is unset.
func timestampField(t gabriel.Timestamp) string {
	if t.IsZero() {
		return ""
	}
	return uintField(uint64(t))
}
