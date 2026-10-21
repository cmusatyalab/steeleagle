package config

import (
	"os"
	"reflect"
	"testing"
)

// TestPluginConfigParsesExample checks that the plugin root and args are parsed
// from a plugin config with no cap.
func TestPluginConfigParsesExample(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	want := PluginConfig{
		Plugin: PluginRoot{
			Name:         "Logdy",
			Description:  "Runs the Logdy logging service",
			Type:         "extra",
			Dependencies: []string{"logdy"},
		},
		Args: []ArgsField{{
			Name:        "timeout",
			Type:        "number",
			Description: "Timeout for disconnection",
			Default:     1.0,
		}},
	}
	if !reflect.DeepEqual(*p, want) {
		t.Errorf("PluginConfig = %+v, want %+v", *p, want)
	}
}

// TestPluginConfigParsesCapExamples checks the plugin root and args of the
// driver and engine plugin configs.
func TestPluginConfigParsesCapExamples(t *testing.T) {
	cases := map[string]struct {
		root PluginRoot
		args []ArgsField
	}{
		"examples/driver.plugin.toml": {
			root: PluginRoot{Name: "Parrot Anafi 4K", Description: "Parrot Anafi 4K quadcopter driver", Type: "driver"},
			args: []ArgsField{{
				Name:        "ip",
				Type:        "string",
				Description: "IP the driver connects to",
				Default:     "192.168.42.1",
			}},
		},
		"examples/engine.plugin.toml": {
			root: PluginRoot{Name: "YOLO Qualcomm", Description: "YOLO detection on QNN-enabled hardware", Type: "engine"},
			args: []ArgsField{{
				Name:        "confidence",
				Type:        "number",
				Description: "Confidence threshold (0.01-1.0)",
				Default:     0.75,
			}},
		},
	}
	for path, want := range cases {
		p, err := ParsePluginConfigFromFilepath(path)
		if err != nil {
			t.Errorf("%s: %v", path, err)
			continue
		}
		if !reflect.DeepEqual(p.Plugin, want.root) {
			t.Errorf("%s: Plugin = %+v, want %+v", path, p.Plugin, want.root)
		}
		if !reflect.DeepEqual(p.Args, want.args) {
			t.Errorf("%s: Args = %+v, want %+v", path, p.Args, want.args)
		}
	}
}

// TestPluginConfigFromBytesMatchesFilepath checks that parsing from bytes and
// from a filepath produce the same config for every plugin example.
func TestPluginConfigFromBytesMatchesFilepath(t *testing.T) {
	for _, path := range []string{
		"examples/plugin.toml",
		"examples/driver.plugin.toml",
		"examples/engine.plugin.toml",
	} {
		content, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		fromBytes, err := ParsePluginConfigFromBytes(content)
		if err != nil {
			t.Errorf("%s: %v", path, err)
			continue
		}
		fromPath, err := ParsePluginConfigFromFilepath(path)
		if err != nil {
			t.Errorf("%s: %v", path, err)
			continue
		}
		if !reflect.DeepEqual(fromBytes, fromPath) {
			t.Errorf("%s: bytes = %+v, filepath = %+v", path, fromBytes, fromPath)
		}
	}
}

// TestPluginConfigRejectsBothCaps checks that a plugin config defining both a
// driver and an engine cap is rejected.
func TestPluginConfigRejectsBothCaps(t *testing.T) {
	content := []byte(`
[plugin]
name = "both"
[driver]
type = "copter"
[engine]
type = "detection"
`)
	if _, err := ParsePluginConfigFromBytes(content); err == nil {
		t.Error("err = nil, want an error")
	}
}

// TestPluginConfigBuildsDriverSets checks that parsing populates the driver
// cap lookup sets.
func TestPluginConfigBuildsDriverSets(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/driver.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	if p.Driver.supportedSet == nil || p.Driver.unsupportedSet == nil {
		t.Error("driver lookup sets were not built")
	}
}

// TestPluginConfigToBytesRoundTrip checks that ToBytes output parses back into
// the same config for every plugin example.
func TestPluginConfigToBytesRoundTrip(t *testing.T) {
	for _, path := range []string{
		"examples/plugin.toml",
		"examples/driver.plugin.toml",
		"examples/engine.plugin.toml",
	} {
		p, err := ParsePluginConfigFromFilepath(path)
		if err != nil {
			t.Errorf("%s: %v", path, err)
			continue
		}
		b, err := p.ToBytes()
		if err != nil {
			t.Errorf("%s: %v", path, err)
			continue
		}
		got, err := ParsePluginConfigFromBytes(b)
		if err != nil {
			t.Errorf("%s: %v", path, err)
			continue
		}
		if !reflect.DeepEqual(got, p) {
			t.Errorf("%s: round trip = %+v, want %+v", path, got, p)
		}
	}
}
