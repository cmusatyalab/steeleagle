package config

import (
	"fmt"
	"os"
	"reflect"
	"strings"
	"testing"
)

// TestFlowConfigParsesExample checks that producers, engines, and edges are
// parsed from the example flow.toml.
func TestFlowConfigParsesExample(t *testing.T) {
	f, err := ParseFlowConfigFromFilepath("examples/flow.toml")
	if err != nil {
		t.Fatal(err)
	}
	tokens := 2
	want := FlowConfig{
		Producers: []Producer{{Name: "telemetry", Tokens: &tokens}},
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

// TestFlowConfigTokensRoundTrip checks that a producer's tokens survive
// ToBytes, and that a producer without tokens is written without them.
func TestFlowConfigTokensRoundTrip(t *testing.T) {
	two := 2
	f := FlowConfig{
		Producers: []Producer{{Name: "front", Tokens: &two}, {Name: "telemetry"}},
		Engines:   []Engine{{Name: "yolo", Location: LocationLocal}},
		Edges: []Edge{
			{From: "front", To: "yolo", Timeout: "100ms"},
			{From: "telemetry", To: "yolo", Timeout: "1m30s"},
		},
	}
	b, err := f.ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	if n := strings.Count(string(b), "tokens"); n != 1 {
		t.Errorf("ToBytes() wrote tokens %d times, want once:\n%s", n, b)
	}
	got, err := ParseFlowConfigFromBytes(b)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(*got, f) {
		t.Errorf("round trip = %+v, want %+v", *got, f)
	}
}

// TestFlowConfigParseRejectsInvalid checks that parsing rejects every flow
// that Uriel rejects.
func TestFlowConfigParseRejectsInvalid(t *testing.T) {
	const (
		producer = "[[producers]]\nname = \"front\"\n"
		engine   = "[[engines]]\nname = \"yolo\"\nlocation = \"local\"\n"
	)
	edge := func(from, to, timeout string) string {
		return fmt.Sprintf("[[edges]]\nfrom = %q\nto = %q\ntimeout = %q\n", from, to, timeout)
	}
	valid := producer + engine + edge("front", "yolo", "2s")
	if _, err := ParseFlowConfigFromBytes([]byte(valid)); err != nil {
		t.Fatalf("ParseFlowConfigFromBytes() of a valid flow = %v, want nil", err)
	}
	if _, err := ParseFlowConfigFromBytes(nil); err != nil {
		t.Errorf("ParseFlowConfigFromBytes() of an empty flow = %v, want nil", err)
	}

	tests := map[string]string{
		"unknown top-level key":         "x = 1\n" + valid,
		"unknown producer key":          "[[producers]]\nname = \"front\"\nfoo = 1\n" + engine + edge("front", "yolo", "2s"),
		"unknown engine key":            producer + "[[engines]]\nname = \"yolo\"\nlocation = \"local\"\nfoo = 1\n" + edge("front", "yolo", "2s"),
		"unknown edge key":              producer + engine + edge("front", "yolo", "2s") + "foo = 1\n",
		"empty producer name":           "[[producers]]\nname = \"\"\n" + engine + edge("", "yolo", "2s"),
		"empty engine name":             producer + "[[engines]]\nname = \"\"\nlocation = \"local\"\n" + edge("front", "", "2s"),
		"duplicate producer":            producer + producer + engine + edge("front", "yolo", "2s"),
		"duplicate engine":              producer + engine + engine + edge("front", "yolo", "2s"),
		"producer and engine same name": producer + "[[engines]]\nname = \"front\"\nlocation = \"local\"\n" + engine + edge("front", "yolo", "2s"),
		"zero tokens":                   "[[producers]]\nname = \"front\"\ntokens = 0\n" + engine + edge("front", "yolo", "2s"),
		"negative tokens":               "[[producers]]\nname = \"front\"\ntokens = -1\n" + engine + edge("front", "yolo", "2s"),
		"missing location":              producer + "[[engines]]\nname = \"yolo\"\n" + edge("front", "yolo", "2s"),
		"unknown location":              producer + "[[engines]]\nname = \"yolo\"\nlocation = \"cloud\"\n" + edge("front", "yolo", "2s"),
		"edge from undeclared node":     valid + edge("nope", "yolo", "2s"),
		"edge to undeclared engine":     valid + edge("front", "nope", "2s"),
		"edge to producer":              valid + edge("yolo", "front", "2s"),
		"duplicate edge":                valid + edge("front", "yolo", "2s"),
		"missing timeout":               producer + engine + "[[edges]]\nfrom = \"front\"\nto = \"yolo\"\n",
		"timeout without unit":          producer + engine + edge("front", "yolo", "2"),
		"zero timeout":                  producer + engine + edge("front", "yolo", "0s"),
		"negative timeout":              producer + engine + edge("front", "yolo", "-1s"),
		"producer feeding no engine":    valid + "[[producers]]\nname = \"idle\"\n",
		"self loop":                     valid + edge("yolo", "yolo", "2s"),
		"cycle": producer + engine + "[[engines]]\nname = \"track\"\nlocation = \"local\"\n" +
			edge("front", "yolo", "2s") + edge("yolo", "track", "2s") + edge("track", "yolo", "2s"),
	}
	for name, flow := range tests {
		if _, err := ParseFlowConfigFromBytes([]byte(flow)); err == nil {
			t.Errorf("ParseFlowConfigFromBytes() with %s = nil, want error", name)
		}
	}
}
