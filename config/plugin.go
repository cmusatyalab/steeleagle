package config

import (
	"bytes"
	"errors"

	"github.com/BurntSushi/toml"
)

type PluginRoot struct {
	// Name of the plugin
	Name string `toml:"name"`
	// Plugin description (optional)
	Description string `toml:"description,omitempty"`
	// Type of the plugin (one of "driver", "engine", "monitor", "simulator", "extra")
	Type string `toml:"type"`
	// List of dependencies for the plugin external to Pixi
	Dependencies []string `toml:"dependencies"`
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
	Args []ArgsField `toml:"args"`
	// Driver cap (if applicable), should have a driver cap, an engine cap, or no cap,
	// both a driver and engine cap defined will result in an error
	Driver *DriverCap `toml:"driver,omitempty"`
	// Engine cap (if applicable)
	Engine *EngineCap `toml:"engine,omitempty"`
}

// ParsePluginConfigFromFilepath parses a plugin.toml from a filepath.
func ParsePluginConfigFromFilepath(filepath string) (*PluginConfig, error) {
	p, err := ParseTomlFromFilepath[PluginConfig](filepath)
	if err != nil {
		return nil, err
	}
	if err := p.Validate(); err != nil {
		return nil, err
	}
	return p, nil
}

// ParsePluginConfigFromBytes parses a plugin.toml from bytes.
func ParsePluginConfigFromBytes(config []byte) (*PluginConfig, error) {
	p, err := ParseTomlFromBytes[PluginConfig](config)
	if err != nil {
		return nil, err
	}
	if err := p.Validate(); err != nil {
		return nil, err
	}
	return p, nil
}

// Validate checks cap exclusivity and builds the driver cap lookup sets. The
// parse functions call it; call it on a PluginConfig built by hand before
// using its driver cap's Supports.
func (p *PluginConfig) Validate() error {
	if p.Driver != nil && p.Engine != nil {
		return errors.New("plugin config cannot define both a driver and an engine cap")
	}
	if p.Driver != nil {
		p.Driver.buildSets()
	}
	return nil
}

// ToBytes writes a PluginConfig to TOML bytes.
func (p *PluginConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(p); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
