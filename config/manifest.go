package config

import (
	"bytes"

	"github.com/BurntSushi/toml"
)

type FlowField struct {
	// Name of the engine
	Name string `toml:"name"`
	// Result proto message id of the engine's output (e.g.
	// "messages/result/DetectionResult")
	Result string `toml:"result"`
}

type InfoField struct {
	// Mission name
	Name string `toml:"name"`
	// Version string (e.g. 1.0.2)
	Version string `toml:"version"`
	// List of roles in the mission
	Roles []string `toml:"roles"`
	// List of squawks in the mission
	Squawks []string `toml:"squawks"`
}

type MissionManifest struct {
	// Basic mission information
	Info InfoField `toml:"info"`
	// List of mission flows
	Flows []FlowField `toml:"flows"`
}

// ParseMissionManifestFromBytes parses a mission manifest from a TOML byte slice.
func ParseMissionManifestFromBytes(content []byte) (*MissionManifest, error) {
	return ParseTomlFromBytes[MissionManifest](content)
}

// ParseMissionManifestFromFilepath parses a mission manifest from a filepath.
func ParseMissionManifestFromFilepath(filepath string) (*MissionManifest, error) {
	return ParseTomlFromFilepath[MissionManifest](filepath)
}

// ToBytes writes a mission manifest to TOML bytes.
func (m *MissionManifest) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	err := toml.NewEncoder(&buf).Encode(m)
	if err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
