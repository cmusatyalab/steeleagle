package config

import (
	"os"
	"reflect"
	"testing"
)

// TestDaemonConfigParsesExample checks that every section of the example
// config.toml is parsed.
func TestDaemonConfigParsesExample(t *testing.T) {
	c, err := ParseDaemonConfigFromFilepath("examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}

	wantDaemon := DaemonRoot{
		Port:         9000,
		Lcs:          9001,
		Logs:         9002,
		Hostname:     "eagled",
		Bind:         "100.64.0.1",
		Orchestrator: "homebase:9000",
	}
	if !reflect.DeepEqual(c.Daemon, wantDaemon) {
		t.Errorf("Daemon = %+v (orchestrator %+v), want %+v (orchestrator %+v)", c.Daemon, c.Daemon.Orchestrator, wantDaemon, wantDaemon.Orchestrator)
	}

	wantSimulator := SimulatorField{
		Package: "github.com/cmusatyalab/steeleagle_plugins//simulator",
		Args: map[string]interface{}{
			"vehicles": []map[string]interface{}{{
				"name":      "cassowary",
				"interface": "steeleagle",
				"origin":    []interface{}{40.33862, -79.86521, 0.0},
				"args":      map[string]interface{}{},
			}},
			"engines": []map[string]interface{}{{
				"name":      "yolo_sim",
				"interface": "detection",
				"args":      map[string]interface{}{},
			}},
			"actors": []map[string]interface{}{{
				"tag":    "person",
				"origin": []interface{}{40.33862, -79.86521, 0.0},
				"waypoints": []interface{}{
					[]interface{}{40.86543, -79.2831, 0.0},
					[]interface{}{40.86541, -79.2835, 0.0},
				},
				"args": map[string]interface{}{"length": int64(1), "width": int64(1), "height": int64(1)},
			}},
		},
	}
	if !reflect.DeepEqual(c.Simulator, wantSimulator) {
		t.Errorf("Simulator = %+v, want %+v", c.Simulator, wantSimulator)
	}

	// Services are sorted into start order: engines, vehicles, then extras
	wantServices := []ServiceField{{
		Name: "yolo",
		Type: ServiceEngine,
		Auth: AuthExternal,
		Plugin: PluginField{
			Plugin:      "yolo_qnn",
			Package:     "github.com/cmusatyalab/steeleagle_plugins//engines/yolo",
			Isolation:   IsolationSandbox,
			Environment: "cuda126",
			Args:        map[string]interface{}{"confidence": 0.7},
		},
	}, {
		Name: "yolo_nq",
		Type: ServiceEngine,
		Auth: AuthExternal,
		Plugin: PluginField{
			Plugin:    "yolo_qnn",
			Package:   "github.com/cmusatyalab/steeleagle_plugins//engines/yolo",
			Isolation: "docker.io/library/alpine:latest",
			Args:      map[string]interface{}{},
		},
	}, {
		Name:     "yolo_sim",
		Type:     ServiceEngine,
		Simulate: true,
		Plugin: PluginField{
			Plugin:  "sim_detector",
			Package: "github.com/cmusatyalab/steeleagle_plugins//simulator",
		},
	}, {
		Name: "harpy",
		Type: ServiceVehicle,
		Auth: AuthAdmin,
		Plugin: PluginField{
			Plugin:  "parrot_anafi",
			Package: "github.com/cmusatyalab/steeleagle_plugins//drivers/parrot@asdef9",
			Args:    map[string]interface{}{"ip": "10.202.0.1"},
		},
	}, {
		Name:     "cassowary",
		Type:     ServiceVehicle,
		Simulate: true,
		Plugin: PluginField{
			Plugin:  "sim_vehicle",
			Package: "github.com/cmusatyalab/steeleagle_plugins//simulator",
		},
	}}
	if !reflect.DeepEqual(c.Services, wantServices) {
		t.Errorf("Services = %+v, want %+v", c.Services, wantServices)
	}
}

// TestDaemonConfigFromBytesMatchesFilepath checks that parsing from bytes and
// from a filepath produce the same config.
func TestDaemonConfigFromBytesMatchesFilepath(t *testing.T) {
	content, err := os.ReadFile("examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}
	fromBytes, err := ParseDaemonConfigFromBytes(content)
	if err != nil {
		t.Fatal(err)
	}
	fromPath, err := ParseDaemonConfigFromFilepath("examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(fromBytes, fromPath) {
		t.Errorf("bytes = %+v, filepath = %+v", fromBytes, fromPath)
	}
}

// TestDaemonConfigToBytesRoundTrip checks that ToBytes output parses back into
// the same config.
func TestDaemonConfigToBytesRoundTrip(t *testing.T) {
	c, err := ParseDaemonConfigFromFilepath("examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}
	b, err := c.ToBytes()
	if err != nil {
		t.Fatal(err)
	}
	got, err := ParseDaemonConfigFromBytes(b)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, c) {
		t.Errorf("round trip = %+v, want %+v", got, c)
	}
}

// TestDaemonConfigValidate checks that duplicate service names are rejected,
// whether the services share a type or not and whether or not they are
// simulated.
func TestDaemonConfigValidate(t *testing.T) {
	c, err := ParseDaemonConfigFromFilepath("examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Validate(); err != nil {
		t.Errorf("Validate() on example = %v, want nil", err)
	}

	p := PluginField{Plugin: "a", Package: "github.com/org/repo"}
	service := func(t ServiceType) ServiceField { return ServiceField{Name: "a", Type: t, Plugin: p} }
	simulated := func(t ServiceType) ServiceField {
		return ServiceField{Name: "a", Type: t, Simulate: true, Plugin: p}
	}
	sim := SimulatorField{Package: "github.com/org/sim"}
	crosses := map[string][]ServiceField{
		"services":           {service(ServiceVehicle), service(ServiceEngine), service(ServiceExtra)},
		"simulated services": {simulated(ServiceVehicle), simulated(ServiceEngine), simulated(ServiceExtra)},
		"simulated and not":  {simulated(ServiceVehicle), service(ServiceEngine)},
	}
	for name, services := range crosses {
		c := DaemonConfig{Simulator: sim, Services: services}
		if err := c.Validate(); err == nil {
			t.Errorf("Validate() with a name shared by %s of different types = nil, want error", name)
		}
	}

	for _, typ := range []ServiceType{ServiceVehicle, ServiceEngine, ServiceExtra} {
		dupes := map[string][]ServiceField{
			"services":           {service(typ), service(typ)},
			"simulated services": {simulated(typ), simulated(typ)},
			"simulated and not":  {simulated(typ), service(typ)},
		}
		for name, services := range dupes {
			c := DaemonConfig{Simulator: sim, Services: services}
			if err := c.Validate(); err == nil {
				t.Errorf("Validate() with duplicate %s %s = nil, want error", typ, name)
			}
		}
	}
}

// TestDaemonConfigValidateAuth checks that every auth level, and no auth, is
// accepted for each kind of service, and that any other auth is rejected.
func TestDaemonConfigValidateAuth(t *testing.T) {
	p := PluginField{Plugin: "a", Package: "github.com/org/repo"}
	configs := func(auth Auth) map[string]DaemonConfig {
		return map[string]DaemonConfig{
			"vehicle": {Services: []ServiceField{{Name: "a", Type: ServiceVehicle, Auth: auth, Plugin: p}}},
			"engine":  {Services: []ServiceField{{Name: "a", Type: ServiceEngine, Auth: auth, Plugin: p}}},
			"extra":   {Services: []ServiceField{{Name: "a", Type: ServiceExtra, Auth: auth, Plugin: p}}},
		}
	}
	for _, auth := range []Auth{"", AuthAdmin, AuthPrivileged, AuthUser, AuthExternal, AuthUnknown} {
		for kind, c := range configs(auth) {
			if err := c.Validate(); err != nil {
				t.Errorf("Validate() with %s auth %q = %v, want nil", kind, auth, err)
			}
		}
	}
	for kind, c := range configs("root") {
		if err := c.Validate(); err == nil {
			t.Errorf("Validate() with %s auth %q = nil, want error", kind, "root")
		}
	}
}

// TestServiceAuthLevel checks that a service with no auth defaults to
// privileged for vehicles and external for engines and extras, and that a set
// auth is kept.
func TestServiceAuthLevel(t *testing.T) {
	defaults := map[ServiceType]Auth{
		ServiceVehicle: AuthPrivileged,
		ServiceEngine:  AuthExternal,
		ServiceExtra:   AuthExternal,
	}
	for typ, want := range defaults {
		if got := (ServiceField{Type: typ}).AuthLevel(); got != want {
			t.Errorf("AuthLevel() of %s with no auth = %q, want %q", typ, got, want)
		}
		if got := (ServiceField{Type: typ, Auth: AuthUser}).AuthLevel(); got != AuthUser {
			t.Errorf("AuthLevel() of %s with auth %q = %q, want %q", typ, AuthUser, got, AuthUser)
		}
	}
}

// TestDaemonConfigValidatePlugin checks that every plugin must define a name
// and a package, simulated or not, and that a simulated service requires a
// simulator, while its plugin's isolation and args are ignored.
func TestDaemonConfigValidatePlugin(t *testing.T) {
	valid := map[string]PluginField{
		"package":                {Plugin: "a", Package: "github.com/org/repo//sub"},
		"package with version":   {Plugin: "a", Package: "github.com/org/repo//sub@main"},
		"package with isolation": {Plugin: "a", Package: "github.com/org/repo", Isolation: IsolationSandbox},
	}
	for name, p := range valid {
		c := DaemonConfig{Services: []ServiceField{{Name: "a", Type: ServiceExtra, Plugin: p}}}
		if err := c.Validate(); err != nil {
			t.Errorf("Validate() with %s plugin = %v, want nil", name, err)
		}
	}

	sim := SimulatorField{Package: "github.com/org/sim"}
	invalid := map[string]PluginField{
		"no plugin":  {Package: "github.com/org/repo"},
		"no package": {Plugin: "a"},
		"empty":      {},
	}
	for name, p := range invalid {
		for _, simulate := range []bool{false, true} {
			c := DaemonConfig{Simulator: sim, Services: []ServiceField{{Name: "a", Type: ServiceVehicle, Simulate: simulate, Plugin: p}}}
			if err := c.Validate(); err == nil {
				t.Errorf("Validate() with %s (simulate = %v) = nil, want error", name, simulate)
			}
		}
	}

	simulated := map[string]PluginField{
		"package":                {Plugin: "a", Package: "github.com/org/sim"},
		"package with isolation": {Plugin: "a", Package: "github.com/org/sim", Isolation: "docker.io/library/alpine:latest"},
		"package with args":      {Plugin: "a", Package: "github.com/org/sim", Args: map[string]interface{}{"x": 1}},
	}
	for name, p := range simulated {
		c := DaemonConfig{Simulator: sim, Services: []ServiceField{{Name: "a", Type: ServiceVehicle, Simulate: true, Plugin: p}}}
		if err := c.Validate(); err != nil {
			t.Errorf("Validate() of a simulated service with %s = %v, want nil", name, err)
		}
	}

	c := DaemonConfig{Services: []ServiceField{{Name: "a", Type: ServiceVehicle, Simulate: true, Plugin: simulated["package"]}}}
	if err := c.Validate(); err == nil {
		t.Error("Validate() of a simulated service with no simulator = nil, want error")
	}
}

// TestDaemonConfigValidateType checks that every service must have a known
// type.
func TestDaemonConfigValidateType(t *testing.T) {
	p := PluginField{Plugin: "a", Package: "github.com/org/repo"}
	for _, typ := range []ServiceType{"", "driver", "Vehicle"} {
		c := DaemonConfig{Services: []ServiceField{{Name: "a", Type: typ, Plugin: p}}}
		if err := c.Validate(); err == nil {
			t.Errorf("Validate() with type %q = nil, want error", typ)
		}
	}
}

// TestDaemonConfigParseRejectsInvalid checks that parsing validates the config.
func TestDaemonConfigParseRejectsInvalid(t *testing.T) {
	content := []byte(`
[[services]]
name = "a"
type = "vehicle"
plugin = { plugin = "a", package = "github.com/org/repo" }

[[services]]
name = "a"
type = "vehicle"
plugin = { plugin = "a", package = "github.com/org/repo" }
`)
	if _, err := ParseDaemonConfigFromBytes(content); err == nil {
		t.Error("ParseDaemonConfigFromBytes() with duplicate vehicles = nil, want error")
	}
}
