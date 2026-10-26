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

// ServiceType is the kind of daemon service.
type ServiceType string

// Service types: a vehicle driver, a compute engine, or any other service.
const (
	ServiceVehicle ServiceType = "vehicle"
	ServiceEngine  ServiceType = "engine"
	ServiceExtra   ServiceType = "extra"
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
	// (defaults to latest). Required unless the service is simulated, and
	// ignored if it is, since simulated services run from the simulator's
	// package
	Package string `toml:"package,omitempty"`
	// Isolation type, either "sandbox" or a container url with tag (optional,
	// ignored if the service is simulated)
	Isolate string `toml:"isolate,omitempty"`
	// Arguments for the plugin
	Args map[string]interface{} `toml:"args"`
}

type ServiceField struct {
	// Name of the service (must be unique among services of its type,
	// simulated or not)
	Name string `toml:"name"`
	// Type of the service (one of: vehicle, engine, extra)
	Type ServiceType `toml:"type"`
	// Auth level of the service (optional, defaults to "unknown")
	Auth Auth `toml:"auth,omitempty"`
	// Whether the service runs in the simulator (optional, defaults to false).
	// A simulated service's plugin comes from the simulator's package, so its
	// package and isolate are ignored
	Simulate bool `toml:"simulate,omitempty"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
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
	// Package url of the simulator, a git repository where a double slash
	// selects a sub directory. A version (commit SHA, branch, or tag) is
	// supported by appending it with an "@", as in Go:
	// github.com/org/repo//sub@v1.0.0 (defaults to latest)
	Package string `toml:"package,omitempty"`
	// Simulated actors
	Actors []SimActorField `toml:"actors"`
}

type DaemonConfig struct {
	// Daemon details
	Daemon DaemonRoot `toml:"daemon"`
	// Daemon simulator service
	Simulator SimulatorField `toml:"simulator,omitempty"`
	// List of daemon services: vehicles, engines and extras, simulated or not
	Services []ServiceField `toml:"services"`
}

// ParseDaemonConfigFromFilepath parses a config.toml from a filepath.
func ParseDaemonConfigFromFilepath(filepath string) (*DaemonConfig, error) {
	d, err := ParseTomlFromFilepath[DaemonConfig](filepath)
	if err != nil {
		return nil, err
	}
	if err := d.Validate(); err != nil {
		return nil, err
	}
	return d, nil
}

// ParseDaemonConfigFromBytes parses a config.toml from bytes.
func ParseDaemonConfigFromBytes(config []byte) (*DaemonConfig, error) {
	d, err := ParseTomlFromBytes[DaemonConfig](config)
	if err != nil {
		return nil, err
	}
	if err := d.Validate(); err != nil {
		return nil, err
	}
	return d, nil
}

// ToBytes writes a DaemonConfig to TOML bytes.
func (d *DaemonConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(d); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// Validate checks that every service is valid and that names are unique
// among services of the same type, simulated or not.
func (d *DaemonConfig) Validate() error {
	names := make(map[ServiceType][]string)
	for _, s := range d.Services {
		if err := s.Validate(); err != nil {
			return fmt.Errorf("%q in services: %w", s.Name, err)
		}
		names[s.Type] = append(names[s.Type], s.Name)
	}
	for _, t := range []ServiceType{ServiceVehicle, ServiceEngine, ServiceExtra} {
		if err := uniqueNames(string(t)+" services", names[t]); err != nil {
			return err
		}
	}
	return nil
}

// Validate checks that the service has a known type and a valid auth, and
// that its plugin has a package unless the service is simulated.
func (s ServiceField) Validate() error {
	if err := s.Type.Validate(); err != nil {
		return err
	}
	if err := s.Auth.Validate(); err != nil {
		return err
	}
	if !s.Simulate && s.Plugin.Package == "" {
		return fmt.Errorf("plugin %q must define a package unless the service is simulated", s.Plugin.Plugin)
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

// Validate checks that the auth is empty or a known level.
func (a Auth) Validate() error {
	switch a.Level() {
	case AuthAdmin, AuthPrivileged, AuthUser, AuthExternal, AuthUnknown:
		return nil
	}
	return fmt.Errorf("invalid auth %q, must be one of %q, %q, %q, %q or %q",
		string(a), AuthAdmin, AuthPrivileged, AuthUser, AuthExternal, AuthUnknown)
}

// Validate checks that the service type is a known type.
func (t ServiceType) Validate() error {
	switch t {
	case ServiceVehicle, ServiceEngine, ServiceExtra:
		return nil
	}
	return fmt.Errorf("invalid service type %q, must be one of %q, %q or %q",
		string(t), ServiceVehicle, ServiceEngine, ServiceExtra)
}

// uniqueNames returns an error if any two names in a list are the same.
func uniqueNames(list string, names []string) error {
	seen := make(map[string]struct{}, len(names))
	for _, n := range names {
		if _, ok := seen[n]; ok {
			return fmt.Errorf("duplicate name %q in %s", n, list)
		}
		seen[n] = struct{}{}
	}
	return nil
}
