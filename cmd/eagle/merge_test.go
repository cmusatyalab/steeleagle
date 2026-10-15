package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/BurntSushi/toml"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
)

// testVehicleConfig is a vehicle's own config, which a flow is merged over.
const testVehicleConfig = `
port-base = 9000

[gabriel]
remote-server = "10.0.0.1:4433"
remote-certificate = "AQ=="

[[gabriel.flow.producers]]
name = "{vehicle}.frames"

[[vehicles]]
name = "harpy"
`

// mergedConfig is what a test reads back of a merged config.
type mergedConfig struct {
	PortBase int `toml:"port-base"`
	Gabriel  struct {
		RemoteServer string              `toml:"remote-server"`
		Flow         vehicle.GabrielFlow `toml:"flow"`
	} `toml:"gabriel"`
	Vehicles []struct {
		Name string `toml:"name"`
	} `toml:"vehicles"`
}

func TestReadConfigMergesEachFlowOverTheVehicle(t *testing.T) {
	base := filepath.Join(t.TempDir(), "drone.toml")
	if err := os.WriteFile(base, []byte(testVehicleConfig), 0o644); err != nil {
		t.Fatal(err)
	}
	flows, err := filepath.Glob(filepath.Join("flows", "*.toml"))
	if err != nil || len(flows) == 0 {
		t.Fatalf("flows = %v, %v", flows, err)
	}
	for _, flow := range flows {
		t.Run(filepath.Base(flow), func(t *testing.T) {
			merged, err := readConfig([]string{base, flow})
			if err != nil {
				t.Fatal(err)
			}
			var cfg mergedConfig
			if _, err := toml.Decode(merged, &cfg); err != nil {
				t.Fatal(err)
			}
			// The vehicle's settings stay, and the flow replaces its flow.
			if cfg.PortBase != 9000 || cfg.Gabriel.RemoteServer != "10.0.0.1:4433" ||
				len(cfg.Vehicles) != 1 || cfg.Vehicles[0].Name != "harpy" {
				t.Errorf("merged config lost the vehicle's settings: %+v", cfg)
			}
			if len(cfg.Gabriel.Flow.Producers) != 2 || len(cfg.Gabriel.Flow.Edges) == 0 {
				t.Errorf("merged flow = %+v, want the flow file's", cfg.Gabriel.Flow)
			}
			gabrielCfg := vehicle.GabrielConfig{
				Flow:              cfg.Gabriel.Flow,
				RemoteServer:      cfg.Gabriel.RemoteServer,
				RemoteCertificate: []byte{1},
			}
			if err := gabrielCfg.Validate(); err != nil {
				t.Errorf("the flow is not valid: %v", err)
			}
		})
	}
}

func TestMergeTablesReplacesArraysAndMergesTables(t *testing.T) {
	dst := map[string]any{
		"kept":  "a",
		"table": map[string]any{"kept": 1, "replaced": 2},
		"array": []any{1, 2},
	}
	mergeTables(dst, map[string]any{
		"table": map[string]any{"replaced": 3},
		"array": []any{4},
	})
	table := dst["table"].(map[string]any)
	if dst["kept"] != "a" || table["kept"] != 1 || table["replaced"] != 3 {
		t.Errorf("tables were not merged key by key: %v", dst)
	}
	if array := dst["array"].([]any); len(array) != 1 || array[0] != 4 {
		t.Errorf("array = %v, want it replaced by [4]", array)
	}
}
