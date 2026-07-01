package vehicle

import (
	"fmt"

	"github.com/pelletier/go-toml/v2"
)

type ControlLawState struct {
	Name    string     `toml:"name" json:"name"`
	Enter   []string   `toml:"enter,omitempty" json:"enter"`
	Allowed []string   `toml:"allowed,omitempty" json:"allowed"`
	Match   [][]string `toml:"match,omitempty" json:"match"`
}

type ControlLaw struct {
	First  string            `toml:"first" json:"first"`
	States []ControlLawState `toml:"states,omitempty" json:"states"`
}

func getLaw(l *ControlLaw) (map[string]ControlLawState, string) {
	// If no start state is provided, ignore and load default laws
	if l == nil || l.First == "" {
		return getDefaultLaw()
	}

	m, err := createLawMap(l)
	if err != nil {
		return getDefaultLaw()
	}

	return m, l.First
}

func getDefaultLaw() (map[string]ControlLawState, string) {
	l, err := parseDefaultLaw()
	if err != nil {
		panic(err)
	}

	m, err := createLawMap(l)
	if err != nil {
		panic(err)
	}

	return m, l.First
}

func createLawMap(l *ControlLaw) (map[string]ControlLawState, error) {
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

func parseDefaultLaw() (*ControlLaw, error) {
	l := &ControlLaw{}
	err := toml.Unmarshal(DefaultLaw, l)
	return l, err
}
