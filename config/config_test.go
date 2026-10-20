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
		Port:         8998,
		Gabriel:      8999,
		Hostname:     "eagled",
		Orchestrator: "homebase",
	}
	if c.Daemon != wantDaemon {
		t.Errorf("Daemon = %+v, want %+v", c.Daemon, wantDaemon)
	}

	wantVehicles := []VehicleField{{
		Name:     "harpy",
		Simulate: false,
		Origin:   []float64{40.413664, -79.949285},
		Plugin: PluginField{
			Plugin:  "parrot_anafi",
			Package: "github.com/cmusatyalab/steeleagle_plugins/drivers/parrot",
			Tag:     "afec80",
			Args:    map[string]interface{}{"ip": "10.202.0.1"},
		},
	}}
	if !reflect.DeepEqual(c.Vehicles, wantVehicles) {
		t.Errorf("Vehicles = %+v, want %+v", c.Vehicles, wantVehicles)
	}

	wantEngines := []ServiceField{{
		Name: "yolo",
		Plugin: PluginField{
			Plugin:  "yolo_qnn",
			Package: "github.com/cmusatyalab/steeleagle_plugins/engines/yolo",
			Tag:     "efcd8e",
			Args:    map[string]interface{}{"confidence": 0.0},
		},
	}}
	if !reflect.DeepEqual(c.Engines, wantEngines) {
		t.Errorf("Engines = %+v, want %+v", c.Engines, wantEngines)
	}

	wantCommanders := []ServiceField{{
		Name: "gcs",
		Plugin: PluginField{
			Plugin:  "gcs",
			Package: "github.com/cmusatyalab/steeleagle_plugins/commanders/gcs",
			Tag:     "abcefd",
			Args:    map[string]interface{}{},
		},
	}}
	if !reflect.DeepEqual(c.Commanders, wantCommanders) {
		t.Errorf("Commanders = %+v, want %+v", c.Commanders, wantCommanders)
	}

	if len(c.Monitors) != 0 {
		t.Errorf("len(Monitors) = %d, want 0", len(c.Monitors))
	}
	if len(c.Extras) != 0 {
		t.Errorf("len(Extras) = %d, want 0", len(c.Extras))
	}

	wantSimulator := ServiceField{
		Name: "aviary",
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
