package config

import (
	"bytes"

	"github.com/BurntSushi/toml"
)

type DaemonRoot struct {
	// Daemon port
	Port int `toml:"port"`
	// Gabriel port
	Gabriel int `toml:"gabriel"`
	// Hostname for this daemon (defaults to "eagled")
	Hostname string `toml:"hostname"`
	// Orchestrator daemon hostname or IP, accepts DNS entries if applicable
	Orchestrator string `toml:"orchestrator,omitempty"`
}

type PluginField struct {
	// Plugin name
	Plugin string `toml:"plugin"`
	// Package url
	Package string `toml:"package"`
	// Tag or commit hash to pull from
	Tag string `toml:"tag,omitempty"`
	// Arguments for the plugin
	Args map[string]interface{} `toml:"args"`
}

type VehicleField struct {
	// Name of the vehicle (must be unique within vehicle services)
	Name string `toml:"name"`
	// Whether or not to simulate the vehicle
	Simulate bool `toml:"simulate,omitempty"`
	// Origin point within the simulator
	Origin []float64 `toml:"origin"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
}

type ServiceField struct {
	// Name of the service (must be unique within this service list)
	Name string `toml:"name"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
}

type DaemonConfig struct {
	// Daemon details
	Daemon DaemonRoot `toml:"daemon"`
	// List of daemon vehicles
	Vehicles []VehicleField `toml:"vehicles"`
	// List of daemon engines
	Engines []ServiceField `toml:"engines"`
	// List of daemon commanders
	Commanders []ServiceField `toml:"commanders"`
	// List of daemon monitors
	Monitors []ServiceField `toml:"monitors"`
	// List of extra daemon services
	Extras []ServiceField `toml:"extras"`
	// Daemon simulator service
	Simulator ServiceField `toml:"simulator,omitempty"`
}

// ParseDaemonConfigFromFilepath parses a config.toml from a filepath.
func ParseDaemonConfigFromFilepath(filepath string) (*DaemonConfig, error) {
	return ParseTomlFromFilepath[DaemonConfig](filepath)
}

// ParseDaemonConfigFromBytes parses a config.toml from bytes.
func ParseDaemonConfigFromBytes(config []byte) (*DaemonConfig, error) {
	return ParseTomlFromBytes[DaemonConfig](config)
}

// ToBytes writes a DaemonConfig to TOML bytes.
func (d *DaemonConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(d); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
