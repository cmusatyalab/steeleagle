package config

import (
	"os"
	"reflect"
	"testing"
)

// TestMissionManifestParsesExample checks that the info and flows sections are
// parsed from the example manifest.toml.
func TestMissionManifestParsesExample(t *testing.T) {
	m, err := ParseMissionManifestFromFilepath("examples/manifest.toml")
	if err != nil {
		t.Fatal(err)
	}
	want := MissionManifest{
		Info: InfoField{
			Name:    "Patrol and Track",
			Version: "0.1.0",
			Roles:   []string{"Patroller", "Tracker"},
			Squawks: []string{"target_found", "done_with_mission"},
		},
		Flows: []FlowField{{
			Name:   "yolo",
			Result: "messages/result/DetectionResult",
		}},
	}
	if !reflect.DeepEqual(*m, want) {
		t.Errorf("MissionManifest = %+v, want %+v", *m, want)
	}
}

// TestMissionManifestFromBytesMatchesFilepath checks that parsing from bytes
// and from a filepath produce the same manifest.
func TestMissionManifestFromBytesMatchesFilepath(t *testing.T) {
	content, err := os.ReadFile("examples/manifest.toml")
	if err != nil {
		t.Fatal(err)
	}
	fromBytes, err := ParseMissionManifestFromBytes(content)
	if err != nil {
		t.Fatal(err)
	}
	fromPath, err := ParseMissionManifestFromFilepath("examples/manifest.toml")
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(fromBytes, fromPath) {
		t.Errorf("bytes = %+v, filepath = %+v", fromBytes, fromPath)
	}
}

// TestMissionManifestToBytesRoundTrip checks that ToBytes output parses back
// into the same manifest.
func TestMissionManifestToBytesRoundTrip(t *testing.T) {
	m, err := ParseMissionManifestFromFilepath("examples/manifest.toml")
	if err != nil {
		t.Fatal(err)
	}
	b, err := m.ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	got, err := ParseMissionManifestFromBytes(b)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, m) {
		t.Errorf("round trip = %+v, want %+v", got, m)
	}
}
