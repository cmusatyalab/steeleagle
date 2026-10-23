package fsm

import (
	"bytes"
	"encoding/json"
	"sync"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// fakeAction is a dsl.Action test double whose Execute behavior is supplied
// by the test.
type fakeAction struct {
	execute func(v sdk.Vehicle) error
}

func (f *fakeAction) Execute(v sdk.Vehicle, _ dsl.MissionData) error { return f.execute(v) }

// fakeEvent is a dsl.Event test double whose Monitor behavior is supplied
// by the test.
type fakeEvent struct {
	monitor func(v sdk.Vehicle) (bool, error)
}

func (f *fakeEvent) Monitor(v sdk.Vehicle, _ dsl.MissionData) (bool, error) { return f.monitor(v) }

// loggingAction is a dsl.Action test double that logs through the mission
// data it is given, then runs execute.
type loggingAction struct {
	execute func(v sdk.Vehicle) error
}

func (l *loggingAction) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	m.Log.Info().Msg("inside action")
	return l.execute(v)
}

// loggingEvent is a dsl.Event test double that logs through the mission
// data it is given, then runs monitor.
type loggingEvent struct {
	monitor func(v sdk.Vehicle) (bool, error)
}

func (l *loggingEvent) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
	m.Log.Info().Msg("inside event")
	return l.monitor(v)
}

// logBuffer collects JSON log lines, safe for concurrent writes.
type logBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *logBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

// entries decodes every log line written so far.
func (b *logBuffer) entries(t *testing.T) []map[string]any {
	t.Helper()
	b.mu.Lock()
	defer b.mu.Unlock()
	var out []map[string]any
	for _, line := range bytes.Split(bytes.TrimSpace(b.buf.Bytes()), []byte("\n")) {
		entry := map[string]any{}
		if err := json.Unmarshal(line, &entry); err != nil {
			t.Fatalf("decoding log line %q: %v", line, err)
		}
		out = append(out, entry)
	}
	return out
}

// requireEntry finds the log entry with message msg and checks that it has
// every field in want, returning it.
func requireEntry(t *testing.T, entries []map[string]any, msg string, want map[string]any) map[string]any {
	t.Helper()
	for _, e := range entries {
		if e["message"] != msg {
			continue
		}
		for k, v := range want {
			if e[k] != v {
				t.Errorf("log %q: %s = %v, want %v (entry %v)", msg, k, e[k], v, e)
			}
		}
		return e
	}
	t.Fatalf("no log entry %q in %v", msg, entries)
	return nil
}
