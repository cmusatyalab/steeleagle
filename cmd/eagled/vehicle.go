package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/cmusatyalab/steeleagle/internal/tailscale"
	"github.com/rs/zerolog/log"
)

// spawnVehicle builds the vehicle's driver plugin, binds its listener on port
// (on its own tsnet node if useVPN), starts the vehicle, and once it's running
// registers it with the swarm controller for exactly as long as it stays up.
//
// The returned stop cancels the vehicle, tearing it down. done is closed once
// that teardown (including the vehicle's own process exit) finishes.
func spawnVehicle(
	ctx context.Context,
	vehicleCfg VehicleConfig,
	port int,
	driverPlugin util.Plugin,
	missionPlugin util.Plugin,
	extraPlugins []util.Plugin,
	authKey string,
	useVPN bool,
	gabrielCfg GabrielConfig,
	swarmCfg SwarmControllerConfig,
	daemonName string,
) (stop context.CancelFunc, done <-chan struct{}, err error) {
	var ln net.Listener
	var dial dialFunc
	var vehicleTS *tailscale.Server
	if useVPN {
		vehicleTS, err = tailscale.NewServer(vehicleCfg.Name, authKey, true)
		if err != nil {
			return nil, nil, fmt.Errorf("starting tailscale for vehicle %s: %w", vehicleCfg.Name, err)
		}
		defer func() {
			if err != nil {
				vehicleTS.Close()
			}
		}()
		ln, err = vehicleTS.Listen("tcp", port)
		dial = vehicleTS.Dial
	} else {
		ln, err = net.Listen("tcp", fmt.Sprintf(":%d", port))
	}
	if err != nil {
		return nil, nil, fmt.Errorf("listening on port %d: %w", port, err)
	}

	videoCfg, err := buildVideoStreamConfig(vehicleCfg)
	if err != nil {
		return nil, nil, fmt.Errorf("configuring video stream for vehicle %s: %w", vehicleCfg.Name, err)
	}

	opts := []vehicle.VehicleOption{
		vehicle.WithName(vehicleCfg.Name),
		vehicle.WithServerListener(ln, nil),
		vehicle.WithVideoStreamConfig(videoCfg),
		vehicle.WithLogger(log.With().Str("vehicle", vehicleCfg.Name).Logger()),
	}
	if gabrielCfg.ServerEndpoint != "" {
		opts = append(opts, vehicle.WithGabrielConfig(vehicle.GabrielConfig{
			ServerEndpoint:           gabrielCfg.ServerEndpoint,
			TelemetryTargetEngines:   gabrielCfg.TelemetryTargetEngines,
			VideoFramesTargetEngines: gabrielCfg.VideoFramesTargetEngines,
		}))
	}

	veh, err := vehicle.NewVehicle(vehicle.PluginConfig{
		Driver:  driverPlugin,
		Mission: missionPlugin,
		Plugins: extraPlugins,
	}, opts...)
	if err != nil {
		return nil, nil, fmt.Errorf("creating vehicle: %w", err)
	}

	vCtx, vCancel := context.WithCancel(ctx)
	if err := veh.Start(vCtx); err != nil {
		vCancel()
		return nil, nil, fmt.Errorf("starting vehicle: %w", err)
	}
	log.Info().Str("vehicle", vehicleCfg.Name).Int("port", port).Msg("vehicle started")

	go registerVehicle(vCtx, swarmCfg.Address, daemonName, vehicleCfg.Name, port, dial)

	doneCh := make(chan struct{})
	go func() {
		defer close(doneCh)
		defer vCancel()
		if err := veh.Wait(); err != nil {
			log.Error().Err(err).Str("vehicle", vehicleCfg.Name).Msg("vehicle exited with error")
		}
		if vehicleTS != nil {
			vehicleTS.Close()
		}
	}()

	return vCancel, doneCh, nil
}

// buildVideoStreamConfig turns vehicleCfg.Video into a
// vehicle.VideoStreamConfig, defaulting StreamType to Frames for simulated
// vehicles and RTSP for everything else, and Resolution to 720p.
func buildVideoStreamConfig(vehicleCfg VehicleConfig) (vehicle.VideoStreamConfig, error) {
	streamType := vehicle.RTSP
	if vehicleCfg.Simulate {
		streamType = vehicle.Frames
	}
	resolution := vehicle.Res720P
	var codec string

	if v := vehicleCfg.Video; v != nil {
		if v.StreamType != "" {
			switch v.StreamType {
			case "rtsp":
				streamType = vehicle.RTSP
			case "frames":
				streamType = vehicle.Frames
			default:
				return vehicle.VideoStreamConfig{}, fmt.Errorf("video.stream-type must be %q or %q, got %q", "rtsp", "frames", v.StreamType)
			}
		}
		if v.Resolution != "" {
			switch v.Resolution {
			case "480p":
				resolution = vehicle.Res480P
			case "720p":
				resolution = vehicle.Res720P
			case "1080p":
				resolution = vehicle.Res1080P
			case "4k":
				resolution = vehicle.Res4K
			default:
				return vehicle.VideoStreamConfig{}, fmt.Errorf("video.resolution must be one of %q, %q, %q, %q, got %q", "480p", "720p", "1080p", "4k", v.Resolution)
			}
		}
		codec = v.Codec
	}

	return vehicle.VideoStreamConfig{
		StreamType: streamType,
		Resolution: resolution,
		Codec:      codec,
	}, nil
}

// aviarySocketPath returns the socket a simulated vehicle's aviary interface
// listens on, matching steeleagle-aviary's interfaces/steeleagle.py
// convention: $XDG_RUNTIME_DIR/steeleagle/plugins/aviary/<name>/services.sock.
func aviarySocketPath(pluginDir, name string) string {
	return filepath.Join(pluginDir, "aviary", name, "services.sock")
}

// installedPluginPath returns the on-disk path to name's binary under
// category's install directory. Category-correctness is enforced
// structurally, not by a lookup: each category has its own directory (see
// util.GetInstalledPluginDir), so a name installed as one category simply
// doesn't exist under another's directory. name == "" returns ("", nil),
// letting callers treat mission/extra slots as optional.
func installedPluginPath(name, category string) (string, error) {
	if name == "" {
		return "", nil
	}
	installDir, err := util.GetInstalledPluginDir(category)
	if err != nil {
		return "", fmt.Errorf("determining install directory: %w", err)
	}
	path := filepath.Join(installDir, name)
	if _, err := os.Stat(path); err != nil {
		return "", fmt.Errorf("plugin %q is not installed as %s: %w", name, category, err)
	}
	return path, nil
}

// newDriverPlugin builds the driver plugin for vehicleCfg: a shim attached
// to the shared aviary simulator's socket for that vehicle if Simulate is
// set, or a plugin installed under PLUGIN_CATEGORY_DRIVER otherwise. Driver
// is ignored when Simulate is true -- including any Args on it, since the
// shim wraps an already-running aviary process rather than spawning one.
func newDriverPlugin(vehicleCfg VehicleConfig, pluginDir string) (util.Plugin, error) {
	if vehicleCfg.Simulate {
		return util.CreateShimPlugin(aviarySocketPath(pluginDir, vehicleCfg.Name), "")
	}
	var name string
	var args []string
	if vehicleCfg.Driver != nil {
		name, args = vehicleCfg.Driver.Name, vehicleCfg.Driver.Args
	}
	path, err := installedPluginPath(name, categoryDriver)
	if err != nil {
		return nil, err
	}
	opts := []util.PluginOption{
		util.WithName(vehicleCfg.Name + "-driver"),
		util.WithPath(path),
	}
	if len(args) > 0 {
		opts = append(opts, util.WithScriptArgs(args))
	}
	return util.CreateBasePlugin(opts...)
}

// newMissionPlugin builds vehicleCfg's mission plugin, if specified.
// WithAuthCode tags it as the mission module.
func newMissionPlugin(vehicleCfg VehicleConfig) (util.Plugin, error) {
	if vehicleCfg.Mission == nil {
		return nil, nil
	}
	path, err := installedPluginPath(vehicleCfg.Mission.Name, categoryMission)
	if err != nil {
		return nil, err
	}
	if path == "" {
		return nil, nil
	}
	opts := []util.PluginOption{
		util.WithName(vehicleCfg.Name + "-mission"),
		util.WithPath(path),
		util.WithAuthCode(util.MissionCode),
	}
	if len(vehicleCfg.Mission.Args) > 0 {
		opts = append(opts, util.WithScriptArgs(vehicleCfg.Mission.Args))
	}
	return util.CreateBasePlugin(opts...)
}

// newExtraPlugins builds every plugin listed in vehicleCfg.Plugins.
func newExtraPlugins(vehicleCfg VehicleConfig) ([]util.Plugin, error) {
	plugins := make([]util.Plugin, 0, len(vehicleCfg.Plugins))
	for _, ref := range vehicleCfg.Plugins {
		path, err := installedPluginPath(ref.Name, categoryExtra)
		if err != nil {
			return nil, err
		}
		opts := []util.PluginOption{
			util.WithName(vehicleCfg.Name + "-" + ref.Name),
			util.WithPath(path),
		}
		if len(ref.Args) > 0 {
			opts = append(opts, util.WithScriptArgs(ref.Args))
		}
		p, err := util.CreateBasePlugin(opts...)
		if err != nil {
			return nil, err
		}
		plugins = append(plugins, p)
	}
	return plugins, nil
}

// resolvePlugins builds vehicleCfg's driver, mission, and extra plugins,
// validating each installed name against its expected category before
// spawnVehicle ever starts a process.
func resolvePlugins(vehicleCfg VehicleConfig, pluginDir string) (driver, mission util.Plugin, extra []util.Plugin, err error) {
	driver, err = newDriverPlugin(vehicleCfg, pluginDir)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("creating driver plugin: %w", err)
	}
	mission, err = newMissionPlugin(vehicleCfg)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("creating mission plugin: %w", err)
	}
	extra, err = newExtraPlugins(vehicleCfg)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("creating extra plugins: %w", err)
	}
	return driver, mission, extra, nil
}
