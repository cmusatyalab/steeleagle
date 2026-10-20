package config

import (
	"bytes"
	"fmt"

	"github.com/BurntSushi/toml"
)

type ControlLawState struct {
	// Name of the state
	Name string `toml:"name" json:"name"`
	// Enter trigger
	Enter []string `toml:"enter" json:"enter"`
	// Allowed commands
	Allowed []string `toml:"allowed" json:"allowed"`
	// Match transitions
	Match [][]string `toml:"match" json:"match"`
}

type ControlLaw struct {
	// First state
	First string `toml:"first" json:"first"`
	// List of states
	States []ControlLawState `toml:"states" json:"states"`
}

// Map returns the law map keyed by state string for a ControlLaw. This is useful
// for easy lookup of states.
func (l *ControlLaw) Map() (map[string]ControlLawState, error) {
	m := make(map[string]ControlLawState)
	for _, value := range l.States {
		if value.Name == "" {
			return nil, fmt.Errorf("unnamed law found in configuration!")
		} else if _, exists := m[value.Name]; exists {
			return nil, fmt.Errorf("duplicate law %v detected!", value.Name)
		}
		m[value.Name] = value
	}
	return m, nil
}

// ParseControlLawFromBytes parses a law TOML from bytes.
func ParseControlLawFromBytes(law []byte) (*ControlLaw, error) {
	return ParseTomlFromBytes[ControlLaw](law)
}

// ParseControlLawFromFilepath parses a law TOML from a filepath.
func ParseControlLawFromFilepath(filepath string) (*ControlLaw, error) {
	return ParseTomlFromFilepath[ControlLaw](filepath)
}

// ToBytes writes a ControlLaw to TOML bytes.
func (l *ControlLaw) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(l); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
