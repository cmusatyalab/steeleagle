package main

import (
	"encoding/base64"
	"fmt"

	"github.com/cmusatyalab/steeleagle/core/vehicle"
)

// TSAuthKeyEnv and TSVehicleAuthKeyEnv are the fixed env var names eagled
// reads its own and every vehicle's tsnet auth key from. If
// TSVehicleAuthKeyEnv is unset, vehicles fall back to TSAuthKeyEnv.
const (
	TSAuthKeyEnv        = "TS_AUTHKEY"
	TSVehicleAuthKeyEnv = "TS_VEHICLE_AUTHKEY"
)

// GabrielConfig models the [gabriel] table: the Gabriel flow every vehicle
// runs, and the remote gabriel-server its remote engines run on.
type GabrielConfig struct {
	// RemoteServer is the host:port of the remote gabriel-server.
	RemoteServer string `toml:"remote-server,omitempty"`
	// RemoteCertificate is the remote server's certificate.der, base64
	// encoded.
	RemoteCertificate string `toml:"remote-certificate,omitempty"`
	// CrossingCapacity is how many inputs each crossing to the remote server
	// may have in flight. Left unset (0), Gabriel picks its default.
	CrossingCapacity int `toml:"crossing-capacity,omitempty"`
	// MaxFrameSize is the largest serialized frame a vehicle sends, in bytes.
	// Left unset (0), vehicle.DefaultGabrielMaxFrameSize.
	MaxFrameSize int `toml:"max-frame-size,omitempty"`
	// Flow is the flow each vehicle runs, with "{vehicle}" standing for the
	// vehicle's name in its names. Left without producers, vehicles run
	// without Gabriel.
	Flow vehicle.GabrielFlow `toml:"flow"`
}

// vehicleConfig returns the config of a vehicle's Gabriel flow, and checks it.
func (c GabrielConfig) vehicleConfig() (vehicle.GabrielConfig, error) {
	certificate, err := base64.StdEncoding.DecodeString(c.RemoteCertificate)
	if err != nil {
		return vehicle.GabrielConfig{}, fmt.Errorf("gabriel.remote-certificate is not base64: %w", err)
	}
	cfg := vehicle.GabrielConfig{
		Flow:              c.Flow,
		RemoteServer:      c.RemoteServer,
		RemoteCertificate: certificate,
		CrossingCapacity:  c.CrossingCapacity,
		MaxFrameSize:      c.MaxFrameSize,
	}
	if err := cfg.Validate(); err != nil {
		return vehicle.GabrielConfig{}, err
	}
	return cfg, nil
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

	// TelemetryFps, if set, requests this telemetry rate from the driver.
	// Left unset (or 0), the driver picks its own default rate.
	TelemetryFps uint32 `toml:"telemetry-fps,omitempty"`
}

// VideoConfig models a [vehicles.video] table.
type VideoConfig struct {
	// StreamType is "rtsp" (forward the driver's own RTSP stream) or "frames"
	// (encode individually sent frames). Defaults per VehicleConfig above if
	// left blank.
	StreamType string `toml:"stream-type,omitempty"`
	// Resolution is one of "360p", "480p", "720p" (default), "1080p", "4k".
	Resolution string `toml:"resolution,omitempty"`
	// Codec, if set, requests hardware decoding from FFmpeg (e.g.
	// "h264_cuvid"). Left blank for software decoding.
	Codec string `toml:"codec,omitempty"`
	// Fps, if set, throttles the video stream to this frame rate. Left
	// unset (or 0) to run unthrottled.
	Fps uint32 `toml:"fps,omitempty"`
}

// Config models the TOML document pushed to eagled via
// DaemonService.Configure. eagled keeps no such file on disk itself.
type Config struct {
	PortBase  int    `toml:"port-base"`            // starting port to assign to vehicles
	PluginDir string `toml:"plugin-dir,omitempty"` // runtime plugin directory
	Hostname  string `toml:"hostname,omitempty"`   // eagled's identity
	// VehicleTsnetMemStore, if true, keeps each vehicle's tsnet state in
	// memory instead of persisting it to disk.
	VehicleTsnetMemStore bool            `toml:"vehicle-tsnet-mem-store,omitempty"`
	Gabriel              GabrielConfig   `toml:"gabriel"`
	Backend              BackendConfig   `toml:"backend"`
	Aviary               AviaryConfig    `toml:"aviary,omitempty"`
	Vehicles             []VehicleConfig `toml:"vehicles"`
}
