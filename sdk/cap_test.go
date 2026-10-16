package sdk

import "testing"

// TestCapParsesPluginAndSupported checks that the top level plugin field and
// the supported services table are parsed from a cap file.
func TestCapParsesPluginAndSupported(t *testing.T) {
	c, err := ParseCapFromFile("cmd/eaglec/testdata/cap.test.toml")
	if err != nil {
		t.Fatal(err)
	}
	if c.Plugin != "driver" {
		t.Errorf("Plugin = %q, want %q", c.Plugin, "driver")
	}
	if len(c.Supported.Services) != 3 {
		t.Errorf("len(Supported.Services) = %d, want 3", len(c.Supported.Services))
	}
}

// TestCapSupports checks that services are opt-in and gate their methods,
// and that everything else is supported unless listed as unsupported.
func TestCapSupports(t *testing.T) {
	c, err := ParseCapFromFile("cmd/eaglec/testdata/cap.test.toml")
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
		if got := c.Supports(name); got != want {
			t.Errorf("Supports(%q) = %v, want %v", name, got, want)
		}
	}
}
