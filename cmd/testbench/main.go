package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"os"
	"path/filepath"

	"github.com/BurntSushi/toml"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog/log"
)

// PluginConfig models a [vehicles.driver] or [vehicles.mission] table, each of
// which points at a plugin and a list of CLI-style arguments for that plugin.
type PluginConfig struct {
	Plugin string   `toml:"plugin"`
	Path   string   `toml:"path,omitempty"`
	Args   []string `toml:"args"`
}

// Vehicle models a single [[vehicles]] entry.
type Vehicle struct {
	Name     string        `toml:"name"`
	Simulate bool          `toml:"simulate,omitempty"`
	Driver   *PluginConfig `toml:"driver"`
	Mission  *PluginConfig `toml:"mission,omitempty"`
}

// GabrielConfig models the [gabriel] table, which configures the Gabriel
// server the vehicles send telemetry and video frames to.
type GabrielConfig struct {
	ServerEndpoint           string   `toml:"server_endpoint"`
	TelemetryTargetEngines   []string `toml:"telemetry_target_engines"`
	VideoFramesTargetEngines []string `toml:"video_frames_target_engines"`
}

// Config models the top-level document: an array of vehicle tables.
type Config struct {
	Vehicles  []Vehicle     `toml:"vehicles"`
	PluginDir string        `toml:"plugin_dir"`
	Gabriel   GabrielConfig `toml:"gabriel,omitempty"`
}

func main() {
	path := flag.String("config", "config.toml", "path to the TOML config file")
	flag.Parse()

	data, err := os.ReadFile(*path)
	if err != nil {
		log.Fatal().Msgf("reading %s: %v", *path, err)
	}

	var cfg Config
	md, err := toml.Decode(string(data), &cfg)
	if err != nil {
		log.Fatal().Msgf("parsing TOML: %v", err)
	}

	// Warn about any keys present in the file that weren't mapped onto the
	// Config struct
	if undecoded := md.Undecoded(); len(undecoded) > 0 {
		fmt.Println("warning: unrecognized keys in config:")
		for _, k := range undecoded {
			fmt.Printf("  - %s\n", k)
		}
	}

	for _, veh := range cfg.Vehicles {
		spawnVehicle(&veh, cfg.PluginDir, cfg.Gabriel)
	}
}

func spawnVehicle(veh *Vehicle, pluginDir string, gabrielCfg GabrielConfig) {
	if veh.Driver == nil {
		log.Fatal().Msgf("driver plugin not specified")
	}
	driverDir := pluginDir
	if veh.Driver.Path != "" {
		driverDir = veh.Driver.Path
	}
	driverPlugin := createDriverPlugin(veh, driverDir)
	var missionPlugin util.Plugin
	if veh.Mission != nil {
		missionDir := pluginDir
		if veh.Mission.Path != "" {
			missionDir = veh.Mission.Path
		}
		missionPlugin = createMissionPlugin(veh, missionDir)
	}

	// Create server listener
	vehiclePath, err := util.GetVehicleDirByName(veh.Name)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't create vehicle path")
	}
	serverLnAddr := filepath.Join(vehiclePath, "server")
	os.Remove(serverLnAddr)
	serverLn, err := net.Listen("unix", serverLnAddr)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't listen on server socket")
	}
	log.Info().Msgf("vehicle %s listening on socket address %s", veh.Name, serverLnAddr)

	// Build plugin config
	pluginConfig := vehicle.PluginConfig{Driver: driverPlugin, Mission: missionPlugin}
	videoConfig := vehicle.VideoStreamConfig{StreamType: vehicle.Frames}
	opts := []vehicle.VehicleOption{
		vehicle.WithName(veh.Name),
		vehicle.WithServerListener(serverLn, nil),
		vehicle.WithVideoStreamConfig(videoConfig),
	}
	if gabrielCfg.ServerEndpoint != "" {
		opts = append(opts, vehicle.WithGabrielConfig(vehicle.GabrielConfig{
			ServerEndpoint:           gabrielCfg.ServerEndpoint,
			TelemetryTargetEngines:   gabrielCfg.TelemetryTargetEngines,
			VideoFramesTargetEngines: gabrielCfg.VideoFramesTargetEngines,
		}))
	}
	vehicle, err := vehicle.NewVehicle(pluginConfig, opts...)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't create vehicle")
	}
	if err := vehicle.Start(context.Background()); err != nil {
		log.Fatal().Err(err).Msgf("vehicle %s failed to start", veh.Name)
	}
	log.Info().Msgf("vehicle %s started!", veh.Name)
	if err := vehicle.Wait(); err != nil {
		log.Fatal().Err(err).Msgf("vehicle %s exited with error", veh.Name)
	}
}

func createDriverPlugin(veh *Vehicle, pluginDir string) util.Plugin {
	var driverPlugin util.Plugin
	if veh.Simulate {
		// Build shim plugin for aviary
		sockPath := filepath.Join(pluginDir, "aviary", veh.Name, "services")
		var err error
		driverPlugin, err = util.CreateShimPlugin(sockPath, "")
		if err != nil {
			log.Fatal().Err(err).Msg("couldn't create aviary plugin")
		}
		log.Info().Msg("using aviary driver plugin")
	} else {
		pluginPath := filepath.Join(pluginDir, "drivers", veh.Driver.Plugin)
		options := []util.PluginOption{
			util.WithName(veh.Name + "-driver"),
			util.WithPath(pluginPath),
		}
		if len(veh.Driver.Args) > 0 {
			options = append(options, util.WithScriptArgs(veh.Driver.Args))
		}
		var err error
		driverPlugin, err = util.CreateBasePlugin(options...)
		if err != nil {
			log.Fatal().Err(err).Msg("couldn't create driver plugin")
		}
		log.Info().Msgf("using %s driver plugin", veh.Driver.Plugin)
	}
	return driverPlugin
}

func createMissionPlugin(veh *Vehicle, pluginDir string) util.Plugin {
	pluginPath := filepath.Join(pluginDir, veh.Mission.Plugin)
	options := []util.PluginOption{
		util.WithName(veh.Name + "-mission"),
		util.WithPath(pluginPath),
		util.WithAuthCode(util.MissionCode),
	}
	if len(veh.Mission.Args) > 0 {
		options = append(options, util.WithScriptArgs(veh.Mission.Args))
	}
	missionPlugin, err := util.CreateBasePlugin(options...)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't create mission plugin")
	}
	return missionPlugin
}
