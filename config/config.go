package config

import (
	"bytes"
	"fmt"

	"github.com/BurntSushi/toml"
)

type DaemonRoot struct {
	// Daemon port
	Port int `toml:"port"`
	// LCS (local compute service) port
	Lcs int `toml:"lcs"`
	// Hostname for this daemon (defaults to "eagled")
	Hostname string `toml:"hostname"`
	// Certificate string for the LCS
	Cert string `toml:"cert"`
	// Orchestrator daemon hostname or IP, accepts DNS entries if applicable
	Orchestrator string `toml:"orchestrator,omitempty"`
}

type PluginField struct {
	// Plugin name
	Plugin string `toml:"plugin"`
	// Package url
	Package string `toml:"package"`
	// Arguments for the plugin
	Args map[string]interface{} `toml:"args"`
}

type VehicleField struct {
	// Name of the vehicle (must be unique within vehicle services)
	Name string `toml:"name"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
}

type EngineField struct {
	// Name of the engine (must be unique within engine services)
	Name string `toml:"name"`
	// Whether this engine is a default flow target for the vehicle (optional)
	DefaultTarget bool `toml:"default_target,omitempty"`
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
	Engines []EngineField `toml:"engines"`
	// List of daemon commanders
	Commanders []ServiceField `toml:"commanders"`
	// List of daemon monitors
	Monitors []ServiceField `toml:"monitors"`
	// List of extra daemon services
	Extras []ServiceField `toml:"extras"`
	// Daemon simulator service
	Simulator ServiceField `toml:"simulator,omitempty"`
}

// DefaultTargets returns the names of the engines marked as default flow
// targets.
func (d *DaemonConfig) DefaultTargets() []string {
	var targets []string
	for _, e := range d.Engines {
		if e.DefaultTarget {
			targets = append(targets, e.Name)
		}
	}
	return targets
}

// ValidateServices checks that the names within each service list are unique.
func (d *DaemonConfig) ValidateServices() error {
	if err := uniqueNames("vehicles", d.Vehicles, func(v VehicleField) string { return v.Name }); err != nil {
		return err
	}
	if err := uniqueNames("engines", d.Engines, func(e EngineField) string { return e.Name }); err != nil {
		return err
	}
	serviceName := func(s ServiceField) string { return s.Name }
	if err := uniqueNames("commanders", d.Commanders, serviceName); err != nil {
		return err
	}
	if err := uniqueNames("monitors", d.Monitors, serviceName); err != nil {
		return err
	}
	return uniqueNames("extras", d.Extras, serviceName)
}

// uniqueNames returns an error if any two fields in a list share a name.
func uniqueNames[T any](list string, fields []T, name func(T) string) error {
	seen := make(map[string]struct{}, len(fields))
	for _, f := range fields {
		n := name(f)
		if _, ok := seen[n]; ok {
			return fmt.Errorf("duplicate name %q in %s", n, list)
		}
		seen[n] = struct{}{}
	}
	return nil
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
