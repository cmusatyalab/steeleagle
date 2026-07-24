package main

import (
	"context"
	"flag"
	"net"
	"os"
	"path/filepath"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog/log"
)

const (
	driverAviary      = "aviary"
	driverParrotAnafi = "parrot-anafi"

	parrotAnafiPluginPathEnv = "PARROT_ANAFI_PLUGIN_PATH"
)

func main() {
	driver := flag.String("driver", driverAviary, "driver plugin to run: aviary or parrot-anafi")
	droneIP := flag.String("ip", "", "ip address of the drone, defaults to the driver's own default if unset (parrot-anafi driver only)")
	parrotAnafiPluginPath := flag.String("parrot-anafi-plugin-path", os.Getenv(parrotAnafiPluginPathEnv), "path to the parrot-anafi driver plugin, can also be set via "+parrotAnafiPluginPathEnv+" (parrot-anafi driver only)")
	flag.Parse()

	name := "test-vehicle"
	pluginPath, err := util.GetPluginDir()
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't get plugin directory")
	}
	vehiclePath, err := util.GetVehicleDirByName(name)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't get vehicle directory")
	}

	var driverPlugin util.Plugin
	switch *driver {
	case driverAviary:
		// Build shim plugin for aviary
		sockPath := filepath.Join(pluginPath, "aviary", name, "services.sock")
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
			options = append(options, util.WithScriptArgs([]string{"--", "--ip", *droneIP}))
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
