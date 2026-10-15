package vehicle

import (
	"encoding/csv"
	"io"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"github.com/BurntSushi/toml"
	gabriel "github.com/cmusatyalab/gabriel/go"
	"github.com/rs/zerolog"
)

func TestGabrielRecorderWritesBenchFormat(t *testing.T) {
	flow := GabrielFlow{
		Producers: []GabrielProducer{{Name: "harpy.frames"}},
		Engines:   []GabrielEngine{{Name: "detector", Location: GabrielRemote}},
		Edges:     []GabrielEdge{{From: "harpy.frames", To: "detector", Timeout: "1s"}},
	}
	recorder, err := newGabrielRecorder(t.TempDir(), "harpy", flow, "10.0.0.1:4433", zerolog.New(io.Discard))
	if err != nil {
		t.Fatal(err)
	}
	const session, seq = 7, 1
	published := gabriel.Timestamp(time.Second)
	recorder.input("harpy.frames", session, seq, published)
	recorder.event("harpy.frames", gabriel.Event{
		Kind:       gabriel.EventResult,
		ID:         gabriel.InputID{Producer: "harpy.frames", Session: session, Seq: seq},
		Engine:     "detector",
		Flow:       "harpy",
		Forward:    gabriel.ForwardStop,
		Result:     []byte("cat"),
		OfferedAt:  gabriel.Timestamp(2 * time.Second),
		At:         gabriel.Timestamp(3 * time.Second),
		ReceivedAt: gabriel.Timestamp(4 * time.Second),
	})
	recorder.event("harpy.frames", gabriel.Event{Kind: gabriel.EventLost, Lost: 2})
	recorder.close()

	inputs := readCSV(t, filepath.Join(recorder.dir, gabrielInputsFile))
	wantInputs := [][]string{gabrielInputsHeader, {"harpy.frames", "7", "1", "1000000000"}}
	if !slices.EqualFunc(inputs, wantInputs, slices.Equal) {
		t.Errorf("inputs.csv = %v, want %v", inputs, wantInputs)
	}
	events := readCSV(t, filepath.Join(recorder.dir, gabrielEventsFile))
	wantEvents := [][]string{
		gabrielEventsHeader,
		{"Result", "harpy.frames", "7", "1", "harpy", "detector", "Stop", "3",
			"2000000000", "3000000000", "4000000000", ""},
		{"Lost", "harpy.frames", "", "", "", "", "", "", "", "", "", "2"},
	}
	if !slices.EqualFunc(events, wantEvents, slices.Equal) {
		t.Errorf("events.csv = %v, want %v", events, wantEvents)
	}

	var run gabrielRun
	if _, err := toml.DecodeFile(filepath.Join(recorder.dir, gabrielRunFile), &run); err != nil {
		t.Fatal(err)
	}
	if run.Remote == nil || run.Remote.Addr != "10.0.0.1:4433" || run.Flow.Engines[0] != flow.Engines[0] {
		t.Errorf("run.toml = %+v, want the flow and its remote server", run)
	}
}

func TestGabrielRecorderStopsWhenFull(t *testing.T) {
	recorder, err := newGabrielRecorder(t.TempDir(), "harpy", GabrielFlow{}, "", zerolog.New(io.Discard))
	if err != nil {
		t.Fatal(err)
	}
	recorder.written.n = gabrielRecordMaxBytes
	// The row that reaches the limit is still written; the next is not.
	recorder.input("harpy.frames", 1, 1, 1)
	recorder.input("harpy.frames", 1, 2, 2)
	recorder.close()

	inputs := readCSV(t, filepath.Join(recorder.dir, gabrielInputsFile))
	if len(inputs) != 2 || inputs[1][2] != "1" {
		t.Errorf("inputs.csv = %v, want the header and input 1", inputs)
	}
}

// readCSV reads every row of the CSV file at path.
func readCSV(t *testing.T, path string) [][]string {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	rows, err := csv.NewReader(f).ReadAll()
	if err != nil {
		t.Fatal(err)
	}
	return rows
}
