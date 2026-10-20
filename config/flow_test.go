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
		Producers: []Producer{{Name: "{vehicle}.telemetry"}},
		Engines:   []Engine{{Name: "{vehicle}.yolo", Location: "local"}},
		Edges: []Edge{{
			From:    "{vehicle}.telemetry",
			To:      "telemetry",
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
