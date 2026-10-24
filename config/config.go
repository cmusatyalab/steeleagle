package config

import (
	"bytes"
	"fmt"

	"github.com/BurntSushi/toml"
)

// Auth is the privilege level that a service's calls to the daemon carry.
type Auth string

// Auth levels, from most to least privileged. A service with no auth is
// AuthUnknown.
const (
	AuthAdmin      Auth = "admin"
	AuthPrivileged Auth = "privileged"
	AuthUser       Auth = "user"
	AuthExternal   Auth = "external"
	AuthUnknown    Auth = "unknown"
)

// IsolateSandbox runs a plugin in a sandbox rather than a container.
const IsolateSandbox = "sandbox"

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
	// Package url, a git repository where a double slash selects a sub
	// directory. A version (commit SHA, branch, or tag) is supported by
	// appending it with an "@", as in Go: github.com/org/repo//sub@v1.0.0
	// (defaults to latest)
	Package string `toml:"package"`
	// Isolation type, either "sandbox" or a container url with tag (optional)
	Isolate string `toml:"isolate,omitempty"`
	// Arguments for the plugin
	Args map[string]interface{} `toml:"args"`
}

type VehicleField struct {
	// Name of the vehicle (must be unique within vehicle services)
	Name string `toml:"name"`
	// Auth level of the service (optional, defaults to "unknown")
	Auth Auth `toml:"auth,omitempty"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
}

type EngineField struct {
	// Name of the engine (must be unique within engine services)
	Name string `toml:"name"`
	// Auth level of the service (optional, defaults to "unknown")
	Auth Auth `toml:"auth,omitempty"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
}

type ServiceField struct {
	// Name of the service (must be unique within this service list)
	Name string `toml:"name"`
	// Auth level of the service (optional, defaults to "unknown")
	Auth Auth `toml:"auth,omitempty"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
}

type SimVehicleField struct {
	// Name of the simulated vehicle (must be unique within simulated vehicles)
	Name string `toml:"name"`
	// Plugin to use
	Plugin string `toml:"plugin"`
	// Origin point (lat, lon, alt)
	Origin [3]float64 `toml:"origin"`
}

type SimEngineField struct {
	// Name of the simulated engine (must be unique within simulated engines)
	Name string `toml:"name"`
	// Plugin to use
	Plugin string `toml:"plugin"`
}

type SimActorField struct {
	// Tag of the actor
	Tag string `toml:"tag"`
	// Waypoints to travel (lat, lon, alt)
	Waypoints [][3]float64 `toml:"waypoints"`
	// Speed to move at (m/s)
	Speed float64 `toml:"speed"`
}

type SimulatorField struct {
	// Simulated vehicles
	Vehicles []SimVehicleField `toml:"vehicles"`
	// Simulated engines
	Engines []SimEngineField `toml:"engines"`
	// Simulated actors
	Actors []SimActorField `toml:"actors"`
}

type DaemonConfig struct {
	// Daemon details
	Daemon DaemonRoot `toml:"daemon"`
	// List of daemon vehicles
	Vehicles []VehicleField `toml:"vehicles"`
	// List of daemon engines
	Engines []EngineField `toml:"engines"`
	// List of extra daemon services
	Extras []ServiceField `toml:"extras"`
	// Daemon simulator service
	Simulator SimulatorField `toml:"simulator,omitempty"`
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

// ValidateServices checks that the names within each service list are unique,
// and that every service has a valid auth and plugin.
func (d *DaemonConfig) ValidateServices() error {
	vehicle := func(v VehicleField) (string, Auth, PluginField) { return v.Name, v.Auth, v.Plugin }
	if err := validateList("vehicles", d.Vehicles, vehicle); err != nil {
		return err
	}
	engine := func(e EngineField) (string, Auth, PluginField) { return e.Name, e.Auth, e.Plugin }
	if err := validateList("engines", d.Engines, engine); err != nil {
		return err
	}
	service := func(s ServiceField) (string, Auth, PluginField) { return s.Name, s.Auth, s.Plugin }
	if err := validateList("extras", d.Extras, service); err != nil {
		return err
	}
	simVehicle := func(v SimVehicleField) string { return v.Name }
	if err := uniqueNames("simulator vehicles", d.Simulator.Vehicles, simVehicle); err != nil {
		return err
	}
	simEngine := func(e SimEngineField) string { return e.Name }
	if err := uniqueNames("simulator engines", d.Simulator.Engines, simEngine); err != nil {
		return err
	}
	return nil
}

// Level returns the auth level, defaulting to AuthUnknown if none is set.
func (a Auth) Level() Auth {
	if a == "" {
		return AuthUnknown
	}
	return a
}

// validate checks that the plugin has a package.
func (p PluginField) validate() error {
	if p.Package == "" {
		return fmt.Errorf("plugin %q must define a package", p.Plugin)
	}
	return nil
}

// validate checks that the auth is empty or a known level.
func (a Auth) validate() error {
	switch a.Level() {
	case AuthAdmin, AuthPrivileged, AuthUser, AuthExternal, AuthUnknown:
		return nil
	}
	return fmt.Errorf("invalid auth %q, must be one of %q, %q, %q, %q or %q",
		string(a), AuthAdmin, AuthPrivileged, AuthUser, AuthExternal, AuthUnknown)
}

// validateList returns an error if any two fields in a list share a name, or
// if any field has an invalid auth or plugin.
func validateList[T any](list string, fields []T, info func(T) (string, Auth, PluginField)) error {
	for _, f := range fields {
		n, auth, plugin := info(f)
		if err := auth.validate(); err != nil {
			return fmt.Errorf("%q in %s: %w", n, list, err)
		}
		if err := plugin.validate(); err != nil {
			return fmt.Errorf("%q in %s: %w", n, list, err)
		}
	}
	return uniqueNames(list, fields, func(f T) string { n, _, _ := info(f); return n })
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
