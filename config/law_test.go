package config

import (
	"os"
	"reflect"
	"testing"
)

// TestControlLawParsesExample checks that the first state and the list of
// states are parsed from the example laws.toml.
func TestControlLawParsesExample(t *testing.T) {
	l, err := ParseControlLawFromFilepath("examples/laws.toml")
	if err != nil {
		t.Fatal(err)
	}
	want := ControlLaw{
		First: "REMOTE",
		States: []ControlLawState{
			{
				Name:    "REMOTE",
				Allowed: []string{},
				Match:   [][]string{{"server/**.MissionService/StartMission", "LOCAL"}},
			},
			{
				Name:    "LOCAL",
				Allowed: []string{},
				Match:   [][]string{},
			},
		},
	}
	if !reflect.DeepEqual(*l, want) {
		t.Errorf("ControlLaw = %+v, want %+v", *l, want)
	}
}

// TestControlLawParsesEnter checks that enter triggers are parsed.
func TestControlLawParsesEnter(t *testing.T) {
	l, err := ParseControlLawFromBytes([]byte(`
first = 'A'
[[states]]
name = 'A'
enter = ['server/**.ControlService/Hold']
`))
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"server/**.ControlService/Hold"}
	if !reflect.DeepEqual(l.States[0].Enter, want) {
		t.Errorf("Enter = %v, want %v", l.States[0].Enter, want)
	}
}

// TestControlLawFromBytesMatchesFilepath checks that parsing from bytes and
// from a filepath produce the same law.
func TestControlLawFromBytesMatchesFilepath(t *testing.T) {
	content, err := os.ReadFile("examples/laws.toml")
	if err != nil {
		t.Fatal(err)
	}
	fromBytes, err := ParseControlLawFromBytes(content)
	if err != nil {
		t.Fatal(err)
	}
	fromPath, err := ParseControlLawFromFilepath("examples/laws.toml")
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(fromBytes, fromPath) {
		t.Errorf("bytes = %+v, filepath = %+v", fromBytes, fromPath)
	}
}

// TestControlLawMap checks that Map keys every state by name.
func TestControlLawMap(t *testing.T) {
	l, err := ParseControlLawFromFilepath("examples/laws.toml")
	if err != nil {
		t.Fatal(err)
	}
	m, err := l.Map()
	if err != nil {
		t.Fatal(err)
	}
	if len(m) != len(l.States) {
		t.Errorf("len(Map) = %d, want %d", len(m), len(l.States))
	}
	for _, s := range l.States {
		got, ok := m[s.Name]
		if !ok {
			t.Errorf("Map missing state %q", s.Name)
			continue
		}
		if !reflect.DeepEqual(got, s) {
			t.Errorf("Map[%q] = %+v, want %+v", s.Name, got, s)
		}
	}
	if _, ok := m[l.First]; !ok {
		t.Errorf("Map missing first state %q", l.First)
	}
}

// TestControlLawMapErrors checks that Map rejects unnamed and duplicate states.
func TestControlLawMapErrors(t *testing.T) {
	cases := map[string]ControlLaw{
		"unnamed":   {States: []ControlLawState{{Name: "A"}, {Name: ""}}},
		"duplicate": {States: []ControlLawState{{Name: "A"}, {Name: "A"}}},
	}
	for label, l := range cases {
		if _, err := l.Map(); err == nil {
			t.Errorf("%s: err = nil, want an error", label)
		}
	}
}

// TestControlLawToBytesRoundTrip checks that ToBytes output parses back into
// the same law.
func TestControlLawToBytesRoundTrip(t *testing.T) {
	l, err := ParseControlLawFromFilepath("examples/laws.toml")
	if err != nil {
		t.Fatal(err)
	}
	b, err := l.ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	got, err := ParseControlLawFromBytes(b)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, l) {
		t.Errorf("round trip = %+v, want %+v", got, l)
	}
}
