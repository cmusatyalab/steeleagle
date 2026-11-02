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
		Type:     "detection",
		Inputs:   []string{"steeleagle_protocol/v1/messages/frame/RawFrame"},
		Forwards: ForwardsAll,
		Result:   "steeleagle_protocol/v1/messages/result/DetectionResult",
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

// TestEngineCapForwards checks that forwards defaults to "*", accepts one of
// the engine's input types, and rejects any other type.
func TestEngineCapForwards(t *testing.T) {
	const (
		raw     = "steeleagle_protocol/v1/messages/frame/RawFrame"
		encoded = "steeleagle_protocol/v1/messages/frame/EncodedFrame"
	)
	cap := func(forwards string) []byte {
		s := "[plugin]\nname = \"e\"\ntype = \"engine\"\n[engine]\ntype = \"detection\"\n" +
			"inputs = [\"" + raw + "\", \"" + encoded + "\"]\n"
		if forwards != "" {
			s += "forwards = \"" + forwards + "\"\n"
		}
		return []byte(s)
	}
	cases := []struct {
		name, forwards, want string
		forwarded            map[string]bool
	}{
		{"default", "", ForwardsAll, map[string]bool{raw: true, encoded: true, "": false}},
		{"all", "*", ForwardsAll, map[string]bool{raw: true, encoded: true, "": false}},
		{"specific", raw, raw, map[string]bool{raw: true, encoded: false, "": false}},
	}
	for _, c := range cases {
		p, err := ParsePluginConfigFromBytes(cap(c.forwards))
		if err != nil {
			t.Errorf("%s: %v", c.name, err)
			continue
		}
		if p.Engine.Forwards != c.want {
			t.Errorf("%s: Forwards = %q, want %q", c.name, p.Engine.Forwards, c.want)
		}
		for input, want := range c.forwarded {
			if got := p.Engine.MatchesForwardedType(input); got != want {
				t.Errorf("%s: MatchesForwardedType(%q) = %v, want %v", c.name, input, got, want)
			}
		}
	}
	if _, err := ParsePluginConfigFromBytes(cap("steeleagle_protocol/v1/messages/result/DetectionResult")); err == nil {
		t.Error("forwards outside inputs: err = nil, want an error")
	}
}
