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
	Args   []string `toml:"args"`
}

// Vehicle models a single [[vehicles]] entry.
type Vehicle struct {
	Name     string        `toml:"name"`
	Simulate bool          `toml:"simulate,omitempty"`
	Driver   *PluginConfig `toml:"driver"`
	Mission  *PluginConfig `toml:"mission,omitempty"`
}

// Config models the top-level document: an array of vehicle tables.
type Config struct {
	Vehicles  []Vehicle `toml:"vehicles"`
	PluginDir string    `toml:"plugin_dir"`
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
		spawnVehicle(&veh, cfg.PluginDir)
	}
}

func spawnVehicle(veh *Vehicle, pluginDir string) {
	if veh.Driver == nil {
		log.Fatal().Msgf("driver plugin not specified")
	}
	driverPlugin := createDriverPlugin(veh, pluginDir)
	var missionPlugin util.Plugin
	if veh.Mission != nil {
		missionPlugin = createMissionPlugin(veh, pluginDir)
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
	vehicle, err := vehicle.NewVehicle(
		pluginConfig,
		vehicle.WithName(veh.Name),
		vehicle.WithServerListener(serverLn, nil),
		vehicle.WithVideoStreamConfig(videoConfig),
	)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't create vehicle")
	}
	vehicle.Start(context.Background())
	log.Info().Msgf("vehicle %s started!", veh.Name)
	vehicle.Wait()
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
