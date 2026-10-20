package config

import (
	"reflect"
	"testing"
)

// TestDriverCapParsesTypeAndSupported checks that the driver type and the
// supported services table are parsed from a driver plugin config.
func TestDriverCapParsesTypeAndSupported(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/driver.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	if p.Driver == nil {
		t.Fatal("Driver = nil, want a driver cap")
	}
	if p.Driver.Type != "copter" {
		t.Errorf("Driver.Type = %q, want %q", p.Driver.Type, "copter")
	}
	if len(p.Driver.Supported.Services) != 3 {
		t.Errorf("len(Driver.Supported.Services) = %d, want 3", len(p.Driver.Supported.Services))
	}
}

// TestDriverCapSupports checks that services are opt-in and gate their methods,
// and that everything else is supported unless listed as unsupported.
func TestDriverCapSupports(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/driver.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	cases := map[string]bool{
		// Listed service and its methods
		"steeleagle_protocol/v1/services/driver/ControlService":         true,
		"steeleagle_protocol/v1/services/driver/ControlService/TakeOff": true,
		// Listed service, but method is unsupported
		"steeleagle_protocol/v1/services/driver/ControlService/Kill": false,
		// Unlisted service and its methods
		"steeleagle_protocol/v1/services/vehicle/SafetyService":        false,
		"steeleagle_protocol/v1/services/vehicle/SafetyService/Arm":    false,
		"steeleagle_protocol/v1/services/mission/MissionService/Start": false,
		// Fields and enums are not gated by services
		"steeleagle_protocol/v1/services/driver/TakeOffRequest/altitude":                  false,
		"steeleagle_protocol/v1/services/driver/ReturnToHomeRequest/final_altitude":       true,
		"steeleagle_protocol/v1/services/control/HeadingMode/HEADING_MODE_START":          false,
		"steeleagle_protocol/v1/services/control/HeadingMode/HEADING_MODE_TO_TARGET":      true,
		"steeleagle_protocol/v1/messages/telemetry/GimbalInfo/angular_velocity_body":      false,
		"steeleagle_protocol/v1/messages/telemetry/PositionInfo/velocity_body/linear_vel": true,
	}
	for name, want := range cases {
		if got := p.Driver.Supports(name); got != want {
			t.Errorf("Supports(%q) = %v, want %v", name, got, want)
		}
	}
}

// TestDriverCapParsesCameras checks that every camera field is parsed from a
// driver plugin config.
func TestDriverCapParsesCameras(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/driver.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	want := []DriverCamera{{
		Name:        "rgb",
		Type:        "steeleagle_protocol/v1/messages/frame/RawFrame",
		Description: "Main RGB camera on gimbal",
		HRes:        1080,
		VRes:        720,
		HFov:        69,
		VFov:        43,
		Fps:         30,
		Latency:     280,
		Gimbal:      true,
		Primary:     true,
	}}
	if !reflect.DeepEqual(p.Driver.Cameras, want) {
		t.Errorf("Driver.Cameras = %+v, want %+v", p.Driver.Cameras, want)
	}
}

// TestDriverCapParsesSupportedAndUnsupported checks that the supported and
// unsupported lists are parsed in full from a driver plugin config.
func TestDriverCapParsesSupportedAndUnsupported(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/driver.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	wantSupported := DriverSupported{Services: []string{
		"steeleagle_protocol/v1/services/driver/ControlService",
		"steeleagle_protocol/v1/services/driver/StreamService",
		"steeleagle_protocol/v1/services/driver/CalibrateService",
	}}
	if !reflect.DeepEqual(p.Driver.Supported, wantSupported) {
		t.Errorf("Driver.Supported = %+v, want %+v", p.Driver.Supported, wantSupported)
	}
	wantUnsupported := DriverUnsupported{
		Methods: []string{
			"steeleagle_protocol/v1/services/driver/ControlService/Kill",
		},
		Fields: []string{
			"steeleagle_protocol/v1/services/driver/TakeOffRequest/altitude",
			"steeleagle_protocol/v1/messages/telemetry/PositionInfo/velocity_body/angular_vel",
			"steeleagle_protocol/v1/messages/telemetry/PositionInfo/velocity_neu/angular_vel",
			"steeleagle_protocol/v1/messages/telemetry/GimbalInfo/angular_velocity_body",
			"steeleagle_protocol/v1/messages/telemetry/GimbalInfo/angular_velocity_neu",
		},
		Enums: []string{
			"steeleagle_protocol/v1/services/control/ReturnToHomeEndBehavior/RETURN_TO_HOME_END_BEHAVIOR_HOVER",
			"steeleagle_protocol/v1/services/control/HeadingMode/HEADING_MODE_START",
		},
	}
	if !reflect.DeepEqual(p.Driver.Unsupported, wantUnsupported) {
		t.Errorf("Driver.Unsupported = %+v, want %+v", p.Driver.Unsupported, wantUnsupported)
	}
}

// TestDriverCapHasService checks that only listed services are hosted, and
// that methods and non-services are not treated as services.
func TestDriverCapHasService(t *testing.T) {
	p, err := ParsePluginConfigFromFilepath("examples/driver.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	cases := map[string]bool{
		"steeleagle_protocol/v1/services/driver/ControlService":         true,
		"steeleagle_protocol/v1/services/driver/StreamService":          true,
		"steeleagle_protocol/v1/services/driver/CalibrateService":       true,
		"steeleagle_protocol/v1/services/driver/ControlService/TakeOff": false,
		"steeleagle_protocol/v1/services/vehicle/SafetyService":         false,
		"steeleagle_protocol/v1/services/driver/TakeOffRequest":         false,
		"": false,
	}
	for name, want := range cases {
		if got := p.Driver.HasService(name); got != want {
			t.Errorf("HasService(%q) = %v, want %v", name, got, want)
		}
	}
}

// TestDriverCapBuildsSetsLazily checks that Supports and HasService work on a
// DriverCap that was not produced by a parse.
func TestDriverCapBuildsSetsLazily(t *testing.T) {
	d := &DriverCap{
		Supported:   DriverSupported{Services: []string{"steeleagle_protocol/v1/services/driver/ControlService"}},
		Unsupported: DriverUnsupported{Methods: []string{"steeleagle_protocol/v1/services/driver/ControlService/Kill"}},
	}
	if !d.HasService("steeleagle_protocol/v1/services/driver/ControlService") {
		t.Error("HasService(ControlService) = false, want true")
	}
	d = &DriverCap{
		Supported:   d.Supported,
		Unsupported: d.Unsupported,
	}
	if d.Supports("steeleagle_protocol/v1/services/driver/ControlService/Kill") {
		t.Error("Supports(ControlService/Kill) = true, want false")
	}
	if !d.Supports("steeleagle_protocol/v1/services/driver/ControlService/Hold") {
		t.Error("Supports(ControlService/Hold) = false, want true")
	}
}

// TestServiceOf checks extraction of the owning service from a type name.
func TestServiceOf(t *testing.T) {
	cases := map[string]struct {
		service string
		ok      bool
	}{
		"steeleagle_protocol/v1/services/driver/ControlService":            {"steeleagle_protocol/v1/services/driver/ControlService", true},
		"steeleagle_protocol/v1/services/driver/ControlService/Kill":       {"steeleagle_protocol/v1/services/driver/ControlService", true},
		"steeleagle_protocol/v1/services/driver/ControlService/Kill/extra": {"steeleagle_protocol/v1/services/driver/ControlService", true},
		"steeleagle_protocol/v1/services/driver/TakeOffRequest/altitude":   {"", false},
		"steeleagle_protocol/v1/services/driver":                           {"", false},
		"steeleagle_protocol/v1/messages/telemetry/GimbalInfo":             {"", false},
		"other/v1/services/driver/ControlService":                          {"", false},
	}
	for name, want := range cases {
		service, ok := serviceOf(name)
		if service != want.service || ok != want.ok {
			t.Errorf("serviceOf(%q) = (%q, %v), want (%q, %v)", name, service, ok, want.service, want.ok)
		}
	}
}
