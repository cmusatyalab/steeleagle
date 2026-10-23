package config

import (
	"os"
	"reflect"
	"testing"
)

// TestFlowConfigParsesExample checks that producers, engines, and edges are
// parsed from the example flow.toml.
func TestFlowConfigParsesExample(t *testing.T) {
	f, err := ParseFlowConfigFromFilepath("examples/flow.toml")
	if err != nil {
		t.Fatal(err)
	}
	want := FlowConfig{
		Producers: []Producer{{Name: "telemetry"}},
		Engines:   []Engine{{Name: "yolo", Location: "local"}},
		Edges: []Edge{{
			From:    "telemetry",
			To:      "yolo",
			Timeout: "2s",
		}},
	}
	if !reflect.DeepEqual(*f, want) {
		t.Errorf("FlowConfig = %+v, want %+v", *f, want)
	}
}

// TestFlowConfigFromBytesMatchesFilepath checks that parsing from bytes and
// from a filepath produce the same flow.
func TestFlowConfigFromBytesMatchesFilepath(t *testing.T) {
	content, err := os.ReadFile("examples/flow.toml")
	if err != nil {
		t.Fatal(err)
	}
	fromBytes, err := ParseFlowConfigFromBytes(content)
	if err != nil {
		t.Fatal(err)
	}
	fromPath, err := ParseFlowConfigFromFilepath("examples/flow.toml")
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(fromBytes, fromPath) {
		t.Errorf("bytes = %+v, filepath = %+v", fromBytes, fromPath)
	}
}

// TestFlowConfigToBytesRoundTrip checks that ToBytes output parses back into
// the same flow.
func TestFlowConfigToBytesRoundTrip(t *testing.T) {
	f, err := ParseFlowConfigFromFilepath("examples/flow.toml")
	if err != nil {
		t.Fatal(err)
	}
	b, err := f.ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	got, err := ParseFlowConfigFromBytes(b)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, f) {
		t.Errorf("round trip = %+v, want %+v", got, f)
	}
}

// TestGetLeafEngines checks that only engines without edges out of them are
// leaves, in declaration order, whether or not edges lead into them.
func TestGetLeafEngines(t *testing.T) {
	f := FlowConfig{
		Producers: []Producer{{Name: "front"}},
		Engines: []Engine{
			{Name: "detect", Location: "local"},
			{Name: "track", Location: "remote"},
			{Name: "segment", Location: "local"},
			{Name: "unused", Location: "local"},
		},
		Edges: []Edge{
			{From: "front", To: "detect"},
			{From: "detect", To: "track"},
			{From: "front", To: "segment"},
		},
	}
	want := []Engine{
		{Name: "track", Location: "remote"},
		{Name: "segment", Location: "local"},
		{Name: "unused", Location: "local"},
	}
	if got := f.GetLeafEngines(); !reflect.DeepEqual(got, want) {
		t.Errorf("GetLeafEngines() = %+v, want %+v", got, want)
	}
	if got := (&FlowConfig{}).GetLeafEngines(); len(got) != 0 {
		t.Errorf("GetLeafEngines() of an empty flow = %+v, want none", got)
	}
}
