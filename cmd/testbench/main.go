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

// PluginConfig models a [vehicles.driver] or [vehicles.mission] table,
// each of which points at a plugin and a list of CLI-style arguments
// for that plugin.
type PluginConfig struct {
	Plugin string   `toml:"plugin"`
	Args   []string `toml:"args"`
}

// Vehicle models a single [[vehicles]] entry.
type Vehicle struct {
	Name     string        `toml:"name"`
	Simulate bool          `toml:"simulate,omitempty"`
	Plugin   string        `toml:"plugin,omitempty"`
	Driver   *PluginConfig `toml:"driver"`
	Mission  *PluginConfig `toml:"mission,omitempty"`
}

// Config models the top-level document: an array of vehicle tables.
type Config struct {
	Vehicles []Vehicle `toml:"vehicles"`
}

func main() {
	path := flag.String("config", "config.toml", "path to the TOML config file")
	flag.Parse()

	data, err := os.ReadFile(*path)
	if err != nil {
		log.Fatalf("reading %s: %v", *path, err)
	}

	var cfg Config
	md, err := toml.Decode(string(data), &cfg)
	if err != nil {
		log.Fatalf("parsing TOML: %v", err)
	}

	// Warn about any keys present in the file that weren't mapped onto
	// the Config struct
	if undecoded := md.Undecoded(); len(undecoded) > 0 {
		fmt.Println("warning: unrecognized keys in config:")
		for _, k := range undecoded {
			fmt.Printf("  - %s\n", k)
		}
	}

	var driverPlugin util.Plugin
	switch *driver {
	case driverAviary:
		// Build shim plugin for aviary
		sockPath := filepath.Join(pluginPath, "aviary", name, "services")
		driverPlugin, err = util.CreateShimPlugin(sockPath, "")
		if err != nil {
			log.Fatal().Err(err).Msg("couldn't create driver plugin")
		}
		log.Info().Msg("shim plugin configured")
	case driverParrotAnafi:
		if *parrotAnafiPluginPath == "" {
			log.Fatal().Msgf("parrot-anafi plugin path not set, use -parrot-anafi-plugin-path or %s", parrotAnafiPluginPathEnv)
		}
		options := []util.PluginOption{
			util.WithName(driverParrotAnafi),
			util.WithPath(*parrotAnafiPluginPath),
		}
		if *droneIP != "" {
			options = append(options, util.WithScriptArgs([]string{"--ip", *droneIP}))
		}
		driverPlugin, err = util.CreateBasePlugin(options...)
		if err != nil {
			log.Fatal().Err(err).Msg("couldn't create driver plugin")
		}
		log.Info().Msg("parrot-anafi plugin configured")
	default:
		log.Fatal().Msgf("unknown driver %q, expected %q or %q", *driver, driverAviary, driverParrotAnafi)
	}

	// Create server listener
	serverLnAddr := filepath.Join(vehiclePath, "server")
	os.Remove(serverLnAddr)
	serverLn, err := net.Listen("unix", serverLnAddr)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't listen on server socket")
	}
	log.Info().Msg("listening on server.sock")

	// Build plugin config
	pluginConfig := vehicle.PluginConfig{Driver: driverPlugin}
	videoConfig := vehicle.VideoStreamConfig{StreamType: vehicle.Frames}
	vehicle, err := vehicle.NewVehicle(
		pluginConfig,
		vehicle.WithName(name),
		vehicle.WithServerListener(serverLn, nil),
		vehicle.WithVideoStreamConfig(videoConfig),
	)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't create vehicle")
	}
	log.Info().Msg("starting vehicle...")
	vehicle.Start(context.Background())
	log.Info().Msg("vehicle started!")
	vehicle.Wait()
}
