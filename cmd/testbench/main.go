package main

import (
	"context"
	"net"
	"os"
	"path/filepath"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog/log"
)

func main() {
	name := "test-vehicle"
	pluginPath, err := util.GetPluginDir()
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't get plugin directory")
	}
	vehiclePath, err := util.GetVehicleDirByName(name)
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't get vehicle directory")
	}

	// Build shim plugin for aviary
	sockPath := filepath.Join(pluginPath, "aviary", name, "services.sock")
	driverPlugin, err := util.CreateShimPlugin(sockPath, "")
	if err != nil {
		log.Fatal().Err(err).Msg("couldn't create driver plugin")
	}
	log.Info().Msg("shim plugin configured")

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
