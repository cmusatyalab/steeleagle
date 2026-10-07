package dsl

import (
	"bytes"
	"os"

	"github.com/BurntSushi/toml"
)

// Engine holds information about a cognitive engine.
type Engine struct {
	// Name of the engine
	Name string `toml:"name"`
	// Location of the engine, either local or remote
	Location string `toml:"location"`
	// Output type of the engine, either RoI, Classification, JSON,
	// or generic bytes
	Output string `toml:"output"`
}

// Info holds basic information about the mission.
type Info struct {
	// Mission name
	Name string `toml:"name"`
	// Version string (e.g. 1.0.2)
	Version string `toml:"version"`
	// Role of this vehicle in the mission
	Role string `toml:"role"`
	// List of roles in the mission
	Roles []string `toml:"roles"`
	// List of squawks in the mission
	Squawks []string `toml:"squawks"`
}

// ManifestFile stores data about the engines, squawks, and roles for a
// mission, which are assigned at compile time.
type ManifestFile struct {
	// Basic mission information
	Info Info `toml:"info"`
	// List of mission engines
	Engines []Engine `toml:"engines"`
}

// ParseManifestFromBytes parses a manifest file from a TOML byte slice.
func ParseManifestFromBytes(content []byte) (*ManifestFile, error) {
	m := &ManifestFile{}
	err := toml.Unmarshal(content, m)
	if err != nil {
		return nil, err
	}
	return m, nil
}

// ParseManifestFromFile parses a manifest file from a filepath.
func ParseManifestFromFile(filepath string) (*ManifestFile, error) {
	content, err := os.ReadFile(filepath)
	if err != nil {
		return nil, err
	}
	return ParseManifestFromBytes(content)
}

// WriteManifestToBytes writes a manifest struct to a TOML byte slice.
func WriteManifestToBytes(manifestFile *ManifestFile) ([]byte, error) {
	var buf bytes.Buffer
	err := toml.NewEncoder(&buf).Encode(manifestFile)
	if err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
