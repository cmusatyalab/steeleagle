package config

import (
	"bytes"

	"github.com/BurntSushi/toml"
)

type Producer struct {
	// Name of the producer
	Name string `toml:"name"`
}

type Engine struct {
	// Name of the engine
	Name string `toml:"name"`
	// Location string (one of: remote, local)
	Location string `toml:"location"`
}

type Edge struct {
	// Start node
	From string `toml:"from"`
	// End node
	To string `toml:"to"`
	// Timeout string literal ("2s", e.g.)
	Timeout string `toml:"timeout"`
}

type FlowConfig struct {
	// Flow graph producers
	Producers []Producer `toml:"producers"`
	// Flow graph engines
	Engines []Engine `toml:"engines"`
	// Flow graph edges
	Edges []Edge `toml:"edges"`
}

// ParseFlowConfigFromBytes parses a flow config from a TOML byte slice.
func ParseFlowConfigFromBytes(content []byte) (*FlowConfig, error) {
	return ParseTomlFromBytes[FlowConfig](content)
}

// ParseFlowConfigFromFilepath parses a flow config from a filepath.
func ParseFlowConfigFromFilepath(filepath string) (*FlowConfig, error) {
	return ParseTomlFromFilepath[FlowConfig](filepath)
}

// GetLeafEngines returns the flow's leaf engines, those with no edges out of
// them, in the order they are declared. Their results are the flow's
// output, since no other engine consumes them.
func (f *FlowConfig) GetLeafEngines() []Engine {
	inner := make(map[string]bool)
	for _, e := range f.Edges {
		inner[e.From] = true
	}
	var leaves []Engine
	for _, e := range f.Engines {
		if !inner[e.Name] {
			leaves = append(leaves, e)
		}
	}
	return leaves
}

// ToBytes writes a FlowConfig to TOML bytes.
func (f *FlowConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(f); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
