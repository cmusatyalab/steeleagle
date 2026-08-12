package main

// TSAuthKeyEnv and TSVehicleAuthKeyEnv are the fixed env var names eagled
// reads its own and every vehicle's tsnet auth key from. If
// TSVehicleAuthKeyEnv is unset, vehicles fall back to TSAuthKeyEnv.
const (
	TSAuthKeyEnv        = "TS_AUTHKEY"
	TSVehicleAuthKeyEnv = "TS_VEHICLE_AUTHKEY"
)

// GabrielConfig models the [gabriel] table.
type GabrielConfig struct {
	ServerEndpoint           string   `toml:"server-endpoint"`
	TelemetryTargetEngines   []string `toml:"telemetry-target-engines,omitempty"`
	VideoFramesTargetEngines []string `toml:"video-frames-target-engines,omitempty"`
}

// SwarmControllerConfig models the [backend.swarm-controller] table.
type SwarmControllerConfig struct {
	Address string `toml:"address"` // host:port of the controller's RegistryService
}

// BackendConfig models the [backend] table.
type BackendConfig struct {
	SwarmController SwarmControllerConfig `toml:"swarm-controller"`
}

// AviaryConfig models the [aviary] table.
type AviaryConfig struct {
	// Command is the command line eagled runs to launch aviary. Defaults to
	// DefaultAviaryCommand.
	Command []string `toml:"command,omitempty"`
	// Dir is the working directory Command runs in.
	Dir string `toml:"dir,omitempty"`
}

// PluginRef names an installed plugin and the rguments to launch it with. Args
// is optional.
type PluginRef struct {
	Name string   `toml:"name"`
	Args []string `toml:"args,omitempty"`
}

// VehicleConfig models a single [[vehicles]] entry, a single vehicle this
// daemon hosts.
type VehicleConfig struct {
	Name      string  `toml:"name"`
	Simulate  bool    `toml:"simulate,omitempty"`  // connect vehicle to shared aviary simulator
	Interface string  `toml:"interface,omitempty"` // aviary driver interface; defaults to DefaultAviaryInterface
	Lat       float64 `toml:"lat,omitempty"`
	Lon       float64 `toml:"lon,omitempty"`
	Alt       float64 `toml:"alt,omitempty"`

	// Driver names a plugin installed via InstallPlugin under
	// PLUGIN_CATEGORY_DRIVER. Required unless Simulate is true, in which case
	// it's ignored and the vehicle instead connects to the shared aviary
	// simulator.
	Driver *PluginRef `toml:"driver,omitempty"`
	// Mission, if set, names a plugin installed via InstallPlugin under
	// PLUGIN_CATEGORY_MISSION. Optional, a vehicle runs fine with no mission
	// plugin.
	Mission *PluginRef `toml:"mission,omitempty"`
	// Plugins names additional plugins installed under
	// PLUGIN_CATEGORY_EXTRA.
	Plugins []PluginRef `toml:"plugins,omitempty"`

	// Video overrides this vehicle's video stream config. If omitted,
	// simulated vehicles default to "frames" and every other vehicle defaults
	// to "rtsp".
	Video *VideoConfig `toml:"video,omitempty"`
}

// VideoConfig models a [vehicles.video] table.
type VideoConfig struct {
	// StreamType is "rtsp" (forward the driver's own RTSP stream) or "frames"
	// (encode individually sent frames). Defaults per VehicleConfig above if
	// left blank.
	StreamType string `toml:"stream-type,omitempty"`
	// Resolution is one of "480p", "720p" (default), "1080p", "4k".
	Resolution string `toml:"resolution,omitempty"`
	// Codec, if set, requests hardware decoding from FFmpeg (e.g.
	// "h264_cuvid"). Left blank for software decoding.
	Codec string `toml:"codec,omitempty"`
}

// Config models the TOML document pushed to eagled via
// DaemonService.Configure. eagled keeps no such file on disk itself.
type Config struct {
	PortBase  int             `toml:"port-base"`            // starting port to assign to vehicles
	PluginDir string          `toml:"plugin-dir,omitempty"` // runtime plugin directory
	Hostname  string          `toml:"hostname,omitempty"`   // eagled's identity
	Gabriel   GabrielConfig   `toml:"gabriel"`
	Backend   BackendConfig   `toml:"backend"`
	Aviary    AviaryConfig    `toml:"aviary,omitempty"`
	Vehicles  []VehicleConfig `toml:"vehicles"`
}
