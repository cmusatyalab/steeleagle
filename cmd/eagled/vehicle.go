package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"time"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/cmusatyalab/steeleagle/internal/tailscale"
	"github.com/rs/zerolog/log"
)

// spawnVehicle builds the vehicle's driver plugin, binds its listener on port
// (on its own tsnet node if authKey is set), starts the vehicle, and once it's
// running registers it with the swarm controller for exactly as long as it
// stays up.
//
// ctx is owned by the caller (daemon.reserve creates it, scoped to this one
// reservation) and used throughout, including the tsnet join and veh.Start:
// canceling it interrupts spawnVehicle even before it returns, not just the
// vehicle once running. done is closed once the vehicle (successfully started)
// exits and finishes tearing down.
func spawnVehicle(
	ctx context.Context,
	vehicleCfg VehicleConfig,
	port int,
	promPort int,
	driverPlugin util.Plugin,
	missionPlugin util.Plugin,
	extraPlugins []util.Plugin,
	authKey string,
	memStore bool,
	gabrielCfg GabrielConfig,
	swarmCfg SwarmControllerConfig,
	daemonName string,
) (done <-chan struct{}, err error) {
	var ln net.Listener
	var dial dialFunc
	var vehicleTS *tailscale.Server
	if authKey != "" {
		startCtx, cancel := context.WithTimeout(ctx, TailscaleStartTimeout)
		defer cancel()
		vehicleTS, err = tailscale.NewServer(startCtx, vehicleCfg.Name, authKey, vehicleCfg.Name, memStore)
		if err != nil {
			return nil, fmt.Errorf("starting tailscale for vehicle %s: %w", vehicleCfg.Name, err)
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
		return nil, fmt.Errorf("listening on port %d: %w", port, err)
	}

	videoCfg, err := buildVideoStreamConfig(vehicleCfg)
	if err != nil {
		return nil, fmt.Errorf("configuring video stream for vehicle %s: %w", vehicleCfg.Name, err)
	}

	opts := []vehicle.VehicleOption{
		vehicle.WithName(vehicleCfg.Name),
		vehicle.WithServerListener(ln, nil),
		vehicle.WithVideoStreamConfig(videoCfg),
		vehicle.WithTelemetryFps(vehicleCfg.TelemetryFps),
		vehicle.WithLogger(log.With().Str("vehicle", vehicleCfg.Name).Logger()),
	}
	if dial != nil {
		// So a MagicDNS gabriel.server-endpoint resolves via the vehicle's own
		// tsnet node, same as swarm-controller registration does, instead of
		// depending on the host's own DNS setup.
		opts = append(opts, vehicle.WithDialer(vehicle.Dialer(dial)))
	}
	if gabrielCfg.ServerEndpoint != "" {
		opts = append(opts, vehicle.WithGabrielConfig(vehicle.GabrielConfig{
			ServerEndpoint:           gabrielCfg.ServerEndpoint,
			TelemetryTargetEngines:   gabrielCfg.TelemetryTargetEngines,
			VideoFramesTargetEngines: gabrielCfg.VideoFramesTargetEngines,
			PrometheusPort:           promPort,
		}))
	}

	veh, err := vehicle.NewVehicle(vehicle.PluginConfig{
		Driver:  driverPlugin,
		Mission: missionPlugin,
		Plugins: extraPlugins,
	}, opts...)
	if err != nil {
		return nil, fmt.Errorf("creating vehicle: %w", err)
	}

	if err := veh.Start(ctx); err != nil {
		return nil, fmt.Errorf("starting vehicle: %w", err)
	}
	log.Info().Str("vehicle", vehicleCfg.Name).Int("port", port).Msg("vehicle started")

	go registerVehicle(ctx, swarmCfg.Address, daemonName, vehicleCfg.Name, port, dial)

	doneCh := make(chan struct{})
	go func() {
		defer close(doneCh)
		if err := veh.Wait(); err != nil {
			log.Error().Err(err).Str("vehicle", vehicleCfg.Name).Msg("vehicle exited with error")
		}
		if vehicleTS != nil {
			vehicleTS.Close()
		}
	}()

	return doneCh, nil
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
	var fps uint32

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
		fps = v.Fps
	}

	return vehicle.VideoStreamConfig{
		StreamType: streamType,
		Resolution: resolution,
		Codec:      codec,
		Fps:        fps,
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

// driverIPFlag is the flag name convention driver plugins use for a real
// drone's IP address (e.g. parrot_anafi's "--ip 192.168.42.1"). Drivers that
// take their target some other way (serial, USB, ...) have no address here to
// probe.
const driverIPFlag = "--ip"

// driverIP extracts the drone IP address from vehicleCfg's driver args, if
// they follow the "--ip <address>" convention. Returns "" if none is found.
func driverIP(vehicleCfg VehicleConfig) string {
	if vehicleCfg.Driver == nil {
		return ""
	}
	args := vehicleCfg.Driver.Args
	for i, arg := range args {
		if arg == driverIPFlag && i+1 < len(args) {
			return args[i+1]
		}
	}
	return ""
}

// droneProbeTimeout bounds how long probeDroneReachable waits for a drone to
// answer an ICMP echo before giving up.
const droneProbeTimeout = 3 * time.Second

// probeDroneReachable pings ip once, returning an error if it doesn't answer
// within droneProbeTimeout. This catches an unreachable drone before eagled
// spends time spawning a driver plugin doomed to fail connecting to it.
func probeDroneReachable(ctx context.Context, ip string) error {
	probeCtx, cancel := context.WithTimeout(ctx, droneProbeTimeout)
	defer cancel()
	timeoutSecs := strconv.Itoa(int(droneProbeTimeout.Seconds()))
	cmd := exec.CommandContext(probeCtx, "ping", "-c", "1", "-W", timeoutSecs, ip)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("drone at %s did not respond to ping: %w", ip, err)
	}
	return nil
}

// droneProbeRetryInterval is how long waitForDrone waits between retries while
// a drone isn't reachable yet.
const droneProbeRetryInterval = 2 * time.Second

// waitForDrone blocks until ip responds to ping, retrying every
// droneProbeRetryInterval, or until ctx is canceled (e.g. the vehicle is
// stopped/forgotten, or the daemon shuts down), whichever comes first.
func waitForDrone(ctx context.Context, vehicleName, ip string) error {
	ticker := time.NewTicker(droneProbeRetryInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			if err := probeDroneReachable(ctx, ip); err == nil {
				log.Info().Str("vehicle", vehicleName).Str("ip", ip).Msg("drone became reachable")
				return nil
			}
		}
	}
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
