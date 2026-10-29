package config

import (
	"bytes"
	"fmt"
	"slices"

	"github.com/BurntSushi/toml"
)

// Auth is the privilege level that a service's calls to the daemon carry.
type Auth string

// Auth levels, from most to least privileged. A service with no auth gets the
// default for its type (see ServiceField.AuthLevel).
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

// IsolationSandbox runs a plugin in a sandbox rather than a container.
const IsolationSandbox = "sandbox"

type DaemonRoot struct {
	// Daemon port
	Port int `toml:"port"`
	// LCS (local compute service) port
	Lcs int `toml:"lcs"`
	// Log port
	Logs int `toml:"logs"`
	// Hostname for this daemon (defaults to "eagled")
	Hostname string `toml:"hostname"`
	// IP address to bind on, as a VPN's (defaults to all interfaces)
	Bind string `toml:"bind,omitempty"`
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
	// (defaults to latest). For a simulated service, this is usually the
	// simulator's package
	Package string `toml:"package,omitempty"`
	// Isolation type, either "sandbox" or a container url with tag (optional,
	// ignored if the service is simulated)
	Isolation string `toml:"isolation,omitempty"`
	// Arguments for the plugin (ignored if the service is simulated)
	Args map[string]interface{} `toml:"args"`
}

type ServiceField struct {
	// Name of the service (must be unique among services of its type,
	// simulated or not)
	Name string `toml:"name"`
	// Type of the service (one of: vehicle, engine, extra)
	Type ServiceType `toml:"type"`
	// Auth level of the service (optional, defaults to "privileged" for
	// vehicles and "external" for engines and extras)
	Auth Auth `toml:"auth,omitempty"`
	// Whether the service runs in the simulator (optional, defaults to false).
	// A simulated service is run by the simulator, configured through the
	// simulator's args, so its plugin's args and isolation are ignored
	Simulate bool `toml:"simulate,omitempty"`
	// Plugin details
	Plugin PluginField `toml:"plugin"`
}

type SimulatorField struct {
	// Package url of the simulator, a git repository where a double slash
	// selects a sub directory. A version (commit SHA, branch, or tag) is
	// supported by appending it with an "@", as in Go:
	// github.com/org/repo//sub@v1.0.0 (defaults to latest)
	Package string `toml:"package,omitempty"`
	// Arguments for the simulator, passed to it like a plugin's args
	Args map[string]interface{} `toml:"args"`
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
	d.sortServices()
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
	d.sortServices()
	return d, nil
}

// serviceOrder is the order services start in: engines first, since vehicles
// use them, then vehicles, then extras.
var serviceOrder = map[ServiceType]int{
	ServiceEngine:  0,
	ServiceVehicle: 1,
	ServiceExtra:   2,
}

// sortServices sorts services into start order by type, keeping the config
// order within each type.
func (d *DaemonConfig) sortServices() {
	slices.SortStableFunc(d.Services, func(a, b ServiceField) int {
		return serviceOrder[a.Type] - serviceOrder[b.Type]
	})
}

// ToBytes writes a DaemonConfig to TOML bytes.
func (d *DaemonConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(d); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// Validate checks that every service is valid, that names are unique across
// all services, whatever their type and whether simulated or not, and that
// there is a simulator if any service is simulated.
func (d *DaemonConfig) Validate() error {
	names := make([]string, 0, len(d.Services))
	for _, s := range d.Services {
		if err := s.Validate(); err != nil {
			return fmt.Errorf("%q in services: %w", s.Name, err)
		}
		if s.Simulate && d.Simulator.Package == "" {
			return fmt.Errorf("%q in services is simulated, but there is no simulator package", s.Name)
		}
		names = append(names, s.Name)
	}
	return uniqueNames("services", names)
}

// Validate checks that the service has a known type and a valid auth, and
// that its plugin has a name and a package.
func (s ServiceField) Validate() error {
	if err := s.Type.Validate(); err != nil {
		return err
	}
	if err := s.Auth.Validate(); err != nil {
		return err
	}
	if s.Plugin.Plugin == "" {
		return fmt.Errorf("no plugin defined")
	}
	if s.Plugin.Package == "" {
		return fmt.Errorf("plugin %q must define a package", s.Plugin.Plugin)
	}
	return nil
}

// AuthLevel returns the auth level of the service, defaulting to
// AuthPrivileged for vehicles and AuthExternal for engines and extras if none
// is set.
func (s ServiceField) AuthLevel() Auth {
	switch {
	case s.Auth != "":
		return s.Auth
	case s.Type == ServiceVehicle:
		return AuthPrivileged
	default:
		return AuthExternal
	}
}

// Validate checks that the auth is empty or a known level.
func (a Auth) Validate() error {
	switch a {
	case "", AuthAdmin, AuthPrivileged, AuthUser, AuthExternal, AuthUnknown:
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
