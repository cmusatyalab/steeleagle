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

	wantVehicles := []VehicleField{{
		Name: "harpy",
		Auth: AuthAdmin,
		Plugin: PluginField{
			Plugin:  "parrot_anafi",
			Package: "github.com/cmusatyalab/steeleagle_plugins/drivers/parrot",
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
			Package: "github.com/cmusatyalab/steeleagle_plugins/engines/yolo",
			Args:    map[string]interface{}{"confidence": 0.0},
		},
	}, {
		Name: "gcs",
		Auth: AuthPrivileged,
		Plugin: PluginField{
			Plugin:  "gcs",
			Package: "github.com/cmusatyalab/steeleagle_plugins/commanders/gcs",
			Args:    map[string]interface{}{},
		},
	}}
	if !reflect.DeepEqual(c.Engines, wantEngines) {
		t.Errorf("Engines = %+v, want %+v", c.Engines, wantEngines)
	}

	if len(c.Monitors) != 0 {
		t.Errorf("len(Monitors) = %d, want 0", len(c.Monitors))
	}
	if len(c.Extras) != 0 {
		t.Errorf("len(Extras) = %d, want 0", len(c.Extras))
	}

	wantSimulator := ServiceField{
		Name: "aviary",
		Auth: AuthExternal,
		Plugin: PluginField{
			Plugin:  "aviary",
			Package: "github.com/cmusatyalab/steeleagle_plugins/simulators/aviary",
		},
	}
	if !reflect.DeepEqual(c.Simulator, wantSimulator) {
		t.Errorf("Simulator = %+v, want %+v", c.Simulator, wantSimulator)
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

	cross := DaemonConfig{
		Vehicles: []VehicleField{{Name: "a"}},
		Engines:  []EngineField{{Name: "a"}},
		Monitors: []ServiceField{{Name: "a"}},
	}
	if err := cross.ValidateServices(); err != nil {
		t.Errorf("ValidateServices() with names shared across lists = %v, want nil", err)
	}

	dupes := map[string]DaemonConfig{
		"vehicles": {Vehicles: []VehicleField{{Name: "a"}, {Name: "a"}}},
		"engines":  {Engines: []EngineField{{Name: "a"}, {Name: "a"}}},
		"monitors": {Monitors: []ServiceField{{Name: "a"}, {Name: "a"}}},
		"extras":   {Extras: []ServiceField{{Name: "a"}, {Name: "a"}}},
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
	configs := func(auth Auth) map[string]DaemonConfig {
		return map[string]DaemonConfig{
			"vehicle":   {Vehicles: []VehicleField{{Name: "a", Auth: auth}}},
			"engine":    {Engines: []EngineField{{Name: "a", Auth: auth}}},
			"monitor":   {Monitors: []ServiceField{{Name: "a", Auth: auth}}},
			"extra":     {Extras: []ServiceField{{Name: "a", Auth: auth}}},
			"simulator": {Simulator: ServiceField{Name: "a", Auth: auth}},
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
