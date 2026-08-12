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
	TelemetryTargetEngines   []string // engines to send telemetry to
	VideoFramesTargetEngines []string // engines to send video frames to
}

type VideoStreamConfig struct {
	Codec      string
	Resolution VideoResolution
	StreamType VideoStreamType
	// Fps is the desired frame rate. If zero, the vehicle stream runs
	// unthrottled at whatever rate the driver (or FFmpeg) produces frames.
	Fps uint32
}
