package vehicle

import (
	"github.com/cmusatyalab/steeleagle/core/util"
)

type PolicyConfig struct {
	Law ControlLaw
}

type PluginConfig struct {
	Driver  util.Plugin
	Mission util.Plugin
	Plugins []util.Plugin
}

// Configuration options for Gabriel client used by the vehicle.
type GabrielConfig struct {
	ServerEndpoint           string   // Gabriel server address
	TelemetryTargetEngines   []string // Engines to send telemetry to
	VideoFramesTargetEngines []string // Engines to send video frames to
}

type VideoStreamConfig struct {
	Codec      string
	Resolution VideoResolution
}
