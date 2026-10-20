package config

import (
	"bytes"

	"github.com/BurntSushi/toml"
)

type Producer struct {
	// Name of the producer
	Name string
}

type Engine struct {
	// Name of the engine
	Name string
	// Location string (one of: remote, local)
	Location string
}

type Edge struct {
	// Start node
	From string
	// End node
	To string
	// Timeout string literal ("2s", e.g.)
	Timeout string
}

type FlowConfig struct {
	// Flow graph producers
	Producers []Producer
	// Flow graph engines
	Engines []Engine
	// Flow graph edges
	Edges []Edge
}

// ParseFlowConfigFromBytes parses a flow config from a TOML byte slice.
func ParseFlowConfigFromBytes(content []byte) (*FlowConfig, error) {
	return ParseTomlFromBytes[FlowConfig](content)
}

// ParseFlowConfigFromFilepath parses a flow config from a filepath.
func ParseFlowConfigFromFilepath(filepath string) (*FlowConfig, error) {
	return ParseTomlFromFilepath[FlowConfig](filepath)
}

// ToBytes writes a FlowConfig to TOML bytes.
func (f *FlowConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(f); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
