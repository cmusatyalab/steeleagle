package main

// TailscaleConfig models the [tailscale] table. eagled's own tsnet node and
// every vehicle's tsnet node can join under separate auth keys. If
// VehicleAuthKeyEnv is left blank, vehicles fall back to AuthKeyEnv.
type TailscaleConfig struct {
	AuthKeyEnv        string `toml:"authkey-env,omitempty"`         // env var holding eagled's own tsnet auth key
	VehicleAuthKeyEnv string `toml:"vehicle-authkey-env,omitempty"` // env var holding every vehicle's tsnet auth key; defaults to AuthKeyEnv
	Hostname          string `toml:"hostname"`                      // eagled's own tsnet hostname
}

// GabrielConfig models the [gabriel] table.
type GabrielConfig struct {
	ServerEndpoint           string   `toml:"server-endpoint"`
	TelemetryTargetEngines   []string `toml:"telemetry-target-engines,omitempty"`
	VideoFramesTargetEngines []string `toml:"video-frames-target-engines,omitempty"`
}

// SwarmControllerConfig models the [backend.swarm-controller] table.
type SwarmControllerConfig struct {
	Address    string `toml:"address"`               // host:port of the controller's RegistryService
	DaemonName string `toml:"daemon-name,omitempty"` // reported to the controller for logging
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

// VehicleConfig models a single [[vehicles]] entry — one vehicle this daemon
// hosts.
type VehicleConfig struct {
	Name      string  `toml:"name"`
	Driver    string  `toml:"driver,omitempty"`
	Simulate  bool    `toml:"simulate,omitempty"`  // connect vehicle to shared aviary simulator
	Interface string  `toml:"interface,omitempty"` // aviary driver interface; defaults to DefaultAviaryInterface
	Lat       float64 `toml:"lat,omitempty"`
	Lon       float64 `toml:"lon,omitempty"`
	Alt       float64 `toml:"alt,omitempty"`

	// Mission, if set, names a plugin installed via InstallPlugin under
	// PLUGIN_CATEGORY_MISSION. Optional -- a vehicle runs fine with no
	// mission plugin.
	Mission string `toml:"mission,omitempty"`
	// Plugins names additional plugins installed under
	// PLUGIN_CATEGORY_EXTRA, started alongside the vehicle but not wired
	// into its ControlService/StreamService/MissionService proxying.
	Plugins []string `toml:"plugins,omitempty"`

	// Video overrides this vehicle's video stream config. If omitted,
	// simulated vehicles default to "frames" and every other vehicle defaults
	// to "rtsp".
	Video *VideoConfig `toml:"video,omitempty"`
}

// VideoConfig models a [vehicles.video] table.
type VideoConfig struct {
	// StreamType is "rtsp" (forward the driver's own RTSP stream) or
	// "frames" (encode individually sent frames). Defaults per VehicleConfig
	// above if left blank.
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
	VPN        bool            `toml:"vpn"`                  // whether eagled's own tsnet node is started
	VehicleVPN bool            `toml:"vehicle-vpn"`          // whether every vehicle gets its own tsnet node
	PortBase   int             `toml:"port-base"`            // starting port to assign to vehicles
	PluginDir  string          `toml:"plugin-dir,omitempty"` // runtime-dir-backed; aviary socket lookup only, not installed plugins (see util.GetInstalledPluginDir)
	Tailscale  TailscaleConfig `toml:"tailscale"`
	Gabriel    GabrielConfig   `toml:"gabriel"`
	Backend    BackendConfig   `toml:"backend"`
	Aviary     AviaryConfig    `toml:"aviary,omitempty"`
	Vehicles   []VehicleConfig `toml:"vehicles"`
}
