package config

import (
	"reflect"
	"testing"
)

// TestEngineCapParsesExample checks that the engine cap is parsed from an
// engine plugin config.
func TestEngineCapParsesExample(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/engine.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	if p.Driver != nil {
		t.Errorf("Driver = %+v, want nil", p.Driver)
	}
	if p.Engine == nil {
		t.Fatal("Engine = nil, want an engine cap")
	}
	want := EngineCap{
		Type:   "detection",
		Inputs: []string{"steeleagle_protocol/v1/messages/frame/RawFrame"},
		Result: "steeleagle_protocol/v1/messages/result/DetectionResult",
	}
	if !reflect.DeepEqual(*p.Engine, want) {
		t.Errorf("Engine = %+v, want %+v", *p.Engine, want)
	}
}

// TestEngineCapMatchesInputType checks input type matching.
func TestEngineCapMatchesInputType(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/engine.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	cases := map[string]bool{
		"steeleagle_protocol/v1/messages/frame/RawFrame":         true,
		"steeleagle_protocol/v1/messages/frame/EncodedFrame":     false,
		"steeleagle_protocol/v1/messages/result/DetectionResult": false,
		"": false,
	}
	for input, want := range cases {
		if got := p.Engine.MatchesInputType(input); got != want {
			t.Errorf("MatchesInputType(%q) = %v, want %v", input, got, want)
		}
	}
}

// TestEngineCapMatchesResultType checks result type matching.
func TestEngineCapMatchesResultType(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/engine.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	cases := map[string]bool{
		"steeleagle_protocol/v1/messages/result/DetectionResult": true,
		"steeleagle_protocol/v1/messages/result/GenericResult":   false,
		"steeleagle_protocol/v1/messages/frame/RawFrame":         false,
		"": false,
	}
	for result, want := range cases {
		if got := p.Engine.MatchesResultType(result); got != want {
			t.Errorf("MatchesResultType(%q) = %v, want %v", result, got, want)
		}
	}
}

// TestEngineCapEmpty checks that an engine cap with no inputs or result
// matches nothing.
func TestEngineCapEmpty(t *testing.T) {
	e := &EngineCap{}
	if e.MatchesInputType("steeleagle_protocol/v1/messages/frame/RawFrame") {
		t.Error("MatchesInputType = true, want false")
	}
	if e.MatchesResultType("steeleagle_protocol/v1/messages/result/DetectionResult") {
		t.Error("MatchesResultType = true, want false")
	}
}
