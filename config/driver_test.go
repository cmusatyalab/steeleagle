package config

import "testing"

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
