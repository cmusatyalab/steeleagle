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
		Producers: []EngineProducer{{
			Name:   "frames",
			Output: "steeleagle_protocol/v1/messages/frame/EncodedFrame",
		}},
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

// TestEngineCapForwards checks that forwards defaults to "*", and that an
// engine forwards one of its input types, or converts its inputs to any
// other type.
func TestEngineCapForwards(t *testing.T) {
	const (
		raw     = "steeleagle_protocol/v1/messages/frame/RawFrame"
		encoded = "steeleagle_protocol/v1/messages/frame/EncodedFrame"
		other   = "steeleagle_protocol/v1/messages/frame/OtherFrame"
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
		converts             bool
	}{
		{"default", "", ForwardsAll, map[string]bool{raw: true, encoded: true, "": false}, false},
		{"all", "*", ForwardsAll, map[string]bool{raw: true, encoded: true, "": false}, false},
		{"specific", raw, raw, map[string]bool{raw: true, encoded: false, "": false}, false},
		{"converts", other, other, map[string]bool{raw: false, encoded: false, other: false}, true},
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
		if got := p.Engine.Converts(); got != c.converts {
			t.Errorf("%s: Converts = %v, want %v", c.name, got, c.converts)
		}
	}
}

// TestEngineCapProducers checks producer lookup and that producers without a
// name or output type, or with a duplicate name, are rejected.
func TestEngineCapProducers(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/engine.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	producer, err := p.Engine.GetProducer("frames")
	if err != nil {
		t.Fatalf("GetProducer(%q) error = %v", "frames", err)
	}
	if producer.Output != "steeleagle_protocol/v1/messages/frame/EncodedFrame" {
		t.Errorf("GetProducer(%q).Output = %q", "frames", producer.Output)
	}
	if _, err := p.Engine.GetProducer("missing"); err == nil {
		t.Errorf("GetProducer(%q) error = nil, want one for a missing producer", "missing")
	}

	cap := func(producers string) []byte {
		return []byte("[plugin]\nname = \"e\"\ntype = \"engine\"\n[engine]\ntype = \"detection\"\n" +
			"inputs = [\"steeleagle_protocol/v1/messages/frame/RawFrame\"]\n" + producers)
	}
	bad := map[string]string{
		"no name":   "[[engine.producers]]\noutput = \"o\"\n",
		"no output": "[[engine.producers]]\nname = \"a\"\n",
		"duplicate": "[[engine.producers]]\nname = \"a\"\noutput = \"o\"\n[[engine.producers]]\nname = \"a\"\noutput = \"o\"\n",
	}
	for name, producers := range bad {
		if _, err := ParsePluginConfigFromBytes(cap(producers)); err == nil {
			t.Errorf("%s: err = nil, want an error", name)
		}
	}
}
