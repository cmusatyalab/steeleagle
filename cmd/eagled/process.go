package main

import (
	"context"
	"os"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// ResetConfig deletes the persisted config and shuts the daemon down, relying
// on the process supervisor to restart it unconfigured. Installed drivers are
// untouched.
func (d *daemon) ResetConfig(ctx context.Context, req *eagledpb.ResetConfigRequest) (*eagledpb.ResetConfigResponse, error) {
	path, err := persistedConfigPath()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "determining config persistence path: %v", err)
	}
	if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
		return nil, status.Errorf(codes.Internal, "clearing persisted config: %v", err)
	}

	d.shutdown()
	return eagledpb.ResetConfigResponse_builder{}.Build(), nil
}

// RestartDaemon shuts the daemon down the same way ResetConfig does, minus
// clearing the persisted config, so the process supervisor brings it back up
// already configured, with its vehicles restarted from applied-config.toml.
func (d *daemon) RestartDaemon(ctx context.Context, req *eagledpb.RestartDaemonRequest) (*eagledpb.RestartDaemonResponse, error) {
	d.shutdown()
	return eagledpb.RestartDaemonResponse_builder{}.Build(), nil
}

// GetStatus reports the daemon's current configuration, if any, and the state
// of every vehicle it knows about.
func (d *daemon) GetStatus(ctx context.Context, req *eagledpb.GetStatusRequest) (*eagledpb.GetStatusResponse, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	resp := eagledpb.GetStatusResponse_builder{Configured: d.configured}
	if d.configured {
		resp.Config = eagledpb.DaemonConfig_builder{
			Vpn:                    d.baseCfg.VPN,
			VehicleVpn:             d.vehicleVPN,
			PortBase:               int32(d.baseCfg.PortBase),
			PluginDir:              d.pluginDir,
			TailscaleHostname:      d.baseCfg.Tailscale.Hostname,
			TailscaleAuthkeyEnv:    d.baseCfg.Tailscale.AuthKeyEnv,
			SwarmControllerAddress: d.swarmCfg.Address,
			DaemonName:             d.daemonName,
			GabrielServerEndpoint:  d.gabrielCfg.ServerEndpoint,
		}.Build()
	}

	vehicles := make([]*eagledpb.VehicleStatus, 0, len(d.vehicleCfgs))
	for name, cfg := range d.vehicleCfgs {
		rv, running := d.running[name]
		port := 0
		if running && rv != nil {
			port = rv.port
		}
		driverName := ""
		if cfg.Driver != nil {
			driverName = cfg.Driver.Name
		}
		vehicles = append(vehicles, eagledpb.VehicleStatus_builder{
			Name:    name,
			Driver:  driverName,
			Running: running && rv != nil,
			Port:    int32(port),
		}.Build())
	}
	resp.Vehicles = vehicles

	return resp.Build(), nil
}
