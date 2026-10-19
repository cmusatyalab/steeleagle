package vehicle

import (
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
)

type PolicyConfig struct {
	Law ControlLaw
}

type PluginConfig struct {
	Driver  plugin.Plugin
	Mission plugin.Plugin
	Plugins []plugin.Plugin
}

// Configuration options for Gabriel client used by the vehicle.
type GabrielConfig struct {
	ServerEndpoint           string   // Gabriel server address
	TelemetryTargetEngines   []string // engines to send telemetry to
	VideoFramesTargetEngines []string // engines to send video frames to
	// PrometheusPort, if set, serves the Gabriel client's Prometheus metrics
	// (input counts, token counts, end-to-end input processing latency) on
	// this port. Left unset (0), no metrics endpoint is served.
	PrometheusPort int
}

type VideoStreamConfig struct {
	Codec      string
	Resolution VideoResolution
	StreamType VideoStreamType
	// Fps is the desired frame rate. If zero, the vehicle stream runs
	// unthrottled at whatever rate the driver (or FFmpeg) produces frames.
	Fps uint32
}
