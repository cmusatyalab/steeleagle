package config

import (
	"bytes"
	"errors"
	"os"

	"github.com/BurntSushi/toml"
)

type PluginRoot struct {
	// Name of the plugin
	Name string `toml:"name"`
	// Plugin description (optional)
	Description string `toml:"description,omitempty"`
	// List of dependencies for the plugin external to Pixi
	Dependencies []string `toml:"dependencies,omitempty"`
}

type ArgsField struct {
	// Name of the argument
	Name string `toml:"name"`
	// JSON type of the argument (one of "string", "number", "object", "array", "boolean")
	Type string `toml:"type"`
	// Argument description (optional)
	Description string `toml:"description,omitempty"`
	// Default value of the argument (optional)
	Default interface{} `toml:"default,omitempty"`
}

type PluginConfig struct {
	// Plugin details
	Plugin PluginRoot `toml:"plugin"`
	// Plugin argument specification (optional)
	Args []ArgsField `toml:"args,omitempty"`
	// Driver cap (if applicable), should have a driver cap, an engine cap, or no cap,
	// both a driver and engine cap defined will result in an error
	Driver *DriverCap `toml:"driver,omitempty"`
	// Engine cap (if applicable)
	Engine *EngineCap `toml:"engine,omitempty"`
}

// ParsePluginConfigFromFilepath parses a plugin.toml from a filepath.
func ParsePluginConfigFromFilepath(filepath string) (*PluginConfig, error) {
	content, err := os.ReadFile(filepath)
	if err != nil {
		return nil, err
	}
	return ParsePluginConfigFromBytes(content)
}

// ParsePluginConfigFromBytes parses a plugin.toml from bytes.
func ParsePluginConfigFromBytes(config []byte) (*PluginConfig, error) {
	p := &PluginConfig{}
	if err := toml.Unmarshal(config, p); err != nil {
		return nil, err
	}
	if p.Driver != nil && p.Engine != nil {
		return nil, errors.New("plugin config cannot define both a driver and an engine cap")
	}
	if p.Driver != nil {
		p.Driver.buildSets()
	}
	return p, nil
}

// ToBytes writes a PluginConfig to TOML bytes.
func (p *PluginConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(p); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
