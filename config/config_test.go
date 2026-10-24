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
		Vehicles: []SimVehicleField{{
			Name:   "cassowary",
			Plugin: "sim_vehicle",
			Origin: [3]float64{40.01654, -79.3402, 0.0},
		}},
		Engines: []SimEngineField{{
			Name:   "sensor_twin",
			Plugin: "sim_detector",
		}},
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

	wantVehicles := []VehicleField{{
		Name: "harpy",
		Auth: AuthAdmin,
		Plugin: PluginField{
			Plugin:  "parrot_anafi",
			Package: "github.com/cmusatyalab/steeleagle_plugins//drivers/parrot@asdef9",
			Args:    map[string]interface{}{"ip": "10.202.0.1"},
		},
	}}
	if !reflect.DeepEqual(c.Vehicles, wantVehicles) {
		t.Errorf("Vehicles = %+v, want %+v", c.Vehicles, wantVehicles)
	}

	wantEngines := []EngineField{{
		Name: "yolo",
		Auth: AuthExternal,
		Plugin: PluginField{
			Plugin:  "yolo_qnn",
			Package: "github.com/cmusatyalab/steeleagle_plugins//engines/yolo",
			Isolate: IsolateSandbox,
			Args:    map[string]interface{}{"confidence": 0.7},
		},
	}, {
		Name: "yolo_nq",
		Auth: AuthExternal,
		Plugin: PluginField{
			Plugin:  "yolo_qnn",
			Package: "github.com/cmusatyalab/steeleagle_plugins//engines/yolo",
			Isolate: "docker.io/library/alpine:latest",
			Args:    map[string]interface{}{},
		},
	}}
	if !reflect.DeepEqual(c.Engines, wantEngines) {
		t.Errorf("Engines = %+v, want %+v", c.Engines, wantEngines)
	}

	if len(c.Extras) != 0 {
		t.Errorf("len(Extras) = %d, want 0", len(c.Extras))
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

// TestValidateServices checks that duplicate names within a service list are
// rejected, while the same name across different lists is allowed.
func TestValidateServices(t *testing.T) {
	c, err := ParseDaemonConfigFromFilepath("examples/config.toml")
	if err != nil {
		t.Fatal(err)
	}
	if err := c.ValidateServices(); err != nil {
		t.Errorf("ValidateServices() on example = %v, want nil", err)
	}

	p := PluginField{Package: "github.com/org/repo"}
	cross := DaemonConfig{
		Vehicles:  []VehicleField{{Name: "a", Plugin: p}},
		Engines:   []EngineField{{Name: "a", Plugin: p}},
		Extras:    []ServiceField{{Name: "a", Plugin: p}},
		Simulator: SimulatorField{Vehicles: []SimVehicleField{{Name: "a"}}, Engines: []SimEngineField{{Name: "a"}}},
	}
	if err := cross.ValidateServices(); err != nil {
		t.Errorf("ValidateServices() with names shared across lists = %v, want nil", err)
	}

	dupes := map[string]DaemonConfig{
		"vehicles":           {Vehicles: []VehicleField{{Name: "a", Plugin: p}, {Name: "a", Plugin: p}}},
		"engines":            {Engines: []EngineField{{Name: "a", Plugin: p}, {Name: "a", Plugin: p}}},
		"extras":             {Extras: []ServiceField{{Name: "a", Plugin: p}, {Name: "a", Plugin: p}}},
		"simulator vehicles": {Simulator: SimulatorField{Vehicles: []SimVehicleField{{Name: "a"}, {Name: "a"}}}},
		"simulator engines":  {Simulator: SimulatorField{Engines: []SimEngineField{{Name: "a"}, {Name: "a"}}}},
	}
	for list, c := range dupes {
		if err := c.ValidateServices(); err == nil {
			t.Errorf("ValidateServices() with duplicate %s = nil, want error", list)
		}
	}
}

// TestValidateServicesAuth checks that every auth level, and no auth, is
// accepted for each kind of service, and that any other auth is rejected.
func TestValidateServicesAuth(t *testing.T) {
	p := PluginField{Package: "github.com/org/repo"}
	configs := func(auth Auth) map[string]DaemonConfig {
		return map[string]DaemonConfig{
			"vehicle": {Vehicles: []VehicleField{{Name: "a", Auth: auth, Plugin: p}}},
			"engine":  {Engines: []EngineField{{Name: "a", Auth: auth, Plugin: p}}},
			"extra":   {Extras: []ServiceField{{Name: "a", Auth: auth, Plugin: p}}},
		}
	}
	for _, auth := range []Auth{"", AuthAdmin, AuthPrivileged, AuthUser, AuthExternal, AuthUnknown} {
		for kind, c := range configs(auth) {
			if err := c.ValidateServices(); err != nil {
				t.Errorf("ValidateServices() with %s auth %q = %v, want nil", kind, auth, err)
			}
		}
	}
	for kind, c := range configs("root") {
		if err := c.ValidateServices(); err == nil {
			t.Errorf("ValidateServices() with %s auth %q = nil, want error", kind, "root")
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

// TestValidateServicesPlugin checks that a plugin must define a package.
func TestValidateServicesPlugin(t *testing.T) {
	valid := map[string]PluginField{
		"package":              {Package: "github.com/org/repo//sub"},
		"package with version": {Package: "github.com/org/repo//sub@main"},
		"package with isolate": {Package: "github.com/org/repo", Isolate: IsolateSandbox},
	}
	for name, p := range valid {
		c := DaemonConfig{Extras: []ServiceField{{Name: "a", Plugin: p}}}
		if err := c.ValidateServices(); err != nil {
			t.Errorf("ValidateServices() with %s plugin = %v, want nil", name, err)
		}
	}

	c := DaemonConfig{Extras: []ServiceField{{Name: "a", Plugin: PluginField{Plugin: "a"}}}}
	if err := c.ValidateServices(); err == nil {
		t.Error("ValidateServices() with no package = nil, want error")
	}
}
