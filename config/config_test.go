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
		Hostname:     "eagled",
		Orchestrator: "homebase:9000",
	}
	if !reflect.DeepEqual(c.Daemon, wantDaemon) {
		t.Errorf("Daemon = %+v (orchestrator %+v), want %+v (orchestrator %+v)", c.Daemon, c.Daemon.Orchestrator, wantDaemon, wantDaemon.Orchestrator)
	}

	wantSimulator := SimulatorField{
		Package: "github.com/cmusatyalab/steeleagle_plugins//simulator",
		Actors: []SimActorField{{
			Tag: "person",
			Waypoints: [][3]float64{
				{40.86543, -79.2831, 0.0},
				{40.86541, -79.2835, 0.0},
			},
			Speed: 3.0,
		}},
	}
	if !reflect.DeepEqual(c.Simulator, wantSimulator) {
		t.Errorf("Simulator = %+v, want %+v", c.Simulator, wantSimulator)
	}

	wantServices := []ServiceField{{
		Name: "harpy",
		Type: ServiceVehicle,
		Auth: AuthAdmin,
		Plugin: PluginField{
			Plugin:  "parrot_anafi",
			Package: "github.com/cmusatyalab/steeleagle_plugins//drivers/parrot@asdef9",
			Args:    map[string]interface{}{"ip": "10.202.0.1"},
		},
	}, {
		Name: "yolo",
		Type: ServiceEngine,
		Auth: AuthExternal,
		Plugin: PluginField{
			Plugin:  "yolo_qnn",
			Package: "github.com/cmusatyalab/steeleagle_plugins//engines/yolo",
			Isolate: IsolateSandbox,
			Args:    map[string]interface{}{"confidence": 0.7},
		},
	}, {
		Name: "yolo_nq",
		Type: ServiceEngine,
		Auth: AuthExternal,
		Plugin: PluginField{
			Plugin:  "yolo_qnn",
			Package: "github.com/cmusatyalab/steeleagle_plugins//engines/yolo",
			Isolate: "docker.io/library/alpine:latest",
			Args:    map[string]interface{}{},
		},
	}, {
		Name:     "cassowary",
		Type:     ServiceVehicle,
		Simulate: true,
		Plugin: PluginField{
			Plugin: "sim_vehicle",
			Args:   map[string]interface{}{"origin": []interface{}{40.33862, -79.86521, 0.0}},
		},
	}, {
		Name:     "yolo_sim",
		Type:     ServiceEngine,
		Simulate: true,
		Plugin: PluginField{
			Plugin: "sim_detector",
			Args:   map[string]interface{}{},
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

// TestDaemonConfigValidate checks that duplicate names among services of one
// type are rejected, whether or not they are simulated, while the same name
// across types is allowed.
func TestDaemonConfigValidate(t *testing.T) {
	c, err := ParseDaemonConfigFromFilepath("examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Validate(); err != nil {
		t.Errorf("Validate() on example = %v, want nil", err)
	}

	p := PluginField{Package: "github.com/org/repo"}
	service := func(t ServiceType) ServiceField { return ServiceField{Name: "a", Type: t, Plugin: p} }
	simulated := func(t ServiceType) ServiceField {
		return ServiceField{Name: "a", Type: t, Simulate: true, Plugin: PluginField{Plugin: "sim"}}
	}
	crosses := map[string][]ServiceField{
		"services":           {service(ServiceVehicle), service(ServiceEngine), service(ServiceExtra)},
		"simulated services": {simulated(ServiceVehicle), simulated(ServiceEngine), simulated(ServiceExtra)},
		"simulated and not":  {simulated(ServiceVehicle), service(ServiceEngine)},
	}
	for name, services := range crosses {
		c := DaemonConfig{Services: services}
		if err := c.Validate(); err != nil {
			t.Errorf("Validate() with a name shared by %s of different types = %v, want nil", name, err)
		}
	}

	for _, typ := range []ServiceType{ServiceVehicle, ServiceEngine, ServiceExtra} {
		dupes := map[string][]ServiceField{
			"services":           {service(typ), service(typ)},
			"simulated services": {simulated(typ), simulated(typ)},
			"simulated and not":  {simulated(typ), service(typ)},
		}
		for name, services := range dupes {
			c := DaemonConfig{Services: services}
			if err := c.Validate(); err == nil {
				t.Errorf("Validate() with duplicate %s %s = nil, want error", typ, name)
			}
		}
	}
}

// TestDaemonConfigValidateAuth checks that every auth level, and no auth, is
// accepted for each kind of service, and that any other auth is rejected.
func TestDaemonConfigValidateAuth(t *testing.T) {
	p := PluginField{Package: "github.com/org/repo"}
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

// TestAuthLevel checks that an empty auth defaults to unknown.
func TestAuthLevel(t *testing.T) {
	if got := Auth("").Level(); got != AuthUnknown {
		t.Errorf("Auth(\"\").Level() = %q, want %q", got, AuthUnknown)
	}
	if got := AuthUser.Level(); got != AuthUser {
		t.Errorf("AuthUser.Level() = %q, want %q", got, AuthUser)
	}
}

// TestDaemonConfigValidatePlugin checks that a plugin must define a package
// unless its service is simulated, in which case the package and isolate are
// ignored.
func TestDaemonConfigValidatePlugin(t *testing.T) {
	valid := map[string]PluginField{
		"package":              {Package: "github.com/org/repo//sub"},
		"package with version": {Package: "github.com/org/repo//sub@main"},
		"package with isolate": {Package: "github.com/org/repo", Isolate: IsolateSandbox},
	}
	for name, p := range valid {
		c := DaemonConfig{Services: []ServiceField{{Name: "a", Type: ServiceExtra, Plugin: p}}}
		if err := c.Validate(); err != nil {
			t.Errorf("Validate() with %s plugin = %v, want nil", name, err)
		}
	}

	c := DaemonConfig{Services: []ServiceField{{Name: "a", Type: ServiceExtra, Plugin: PluginField{Plugin: "a"}}}}
	if err := c.Validate(); err == nil {
		t.Error("Validate() with no package = nil, want error")
	}

	simulated := map[string]PluginField{
		"no package":           {Plugin: "a"},
		"package":              {Plugin: "a", Package: "github.com/org/repo"},
		"isolate":              {Plugin: "a", Isolate: IsolateSandbox},
		"package with isolate": {Plugin: "a", Package: "github.com/org/repo", Isolate: "docker.io/library/alpine:latest"},
	}
	for name, p := range simulated {
		c := DaemonConfig{Services: []ServiceField{{Name: "a", Type: ServiceVehicle, Simulate: true, Plugin: p}}}
		if err := c.Validate(); err != nil {
			t.Errorf("Validate() of a simulated service with %s = %v, want nil", name, err)
		}
	}
}

// TestDaemonConfigValidateType checks that every service must have a known
// type.
func TestDaemonConfigValidateType(t *testing.T) {
	p := PluginField{Package: "github.com/org/repo"}
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
