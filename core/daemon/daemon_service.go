package daemon

import (
	"context"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// RegisterOrchestrator registers this daemon as the orchestrator for another daemon.
func (d *Daemon) RegisterOrchestrator(
	ctx context.Context,
	req *daemonpb.RegisterOrchestratorRequest,
) (*daemonpb.RegisterOrchestratorResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "RegisterOrchestrator not implemented")
}

// Configure loads a TOML config and restarts the daemon with it.
func (d *Daemon) Configure(
	ctx context.Context,
	req *daemonpb.ConfigureRequest,
) (*daemonpb.ConfigureResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "Configure not implemented")
}

// GetConfiguration returns the current TOML config as bytes.
func (d *Daemon) GetConfiguration(
	ctx context.Context,
	req *daemonpb.GetConfigurationRequest,
) (*daemonpb.GetConfigurationResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "GetConfiguration not implemented")
}

// ResetConfiguration replaces the current TOML config with the default config.
func (d *Daemon) ResetConfiguration(
	ctx context.Context,
	req *daemonpb.ResetConfigurationRequest,
) (*daemonpb.ResetConfigurationResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "ResetConfiguration not implemented")
}

// ListServices lists all active daemon services and their cap files.
func (d *Daemon) ListServices(
	ctx context.Context,
	req *daemonpb.ListServicesRequest,
) (*daemonpb.ListServicesResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "ListServices not implemented")
}

// RestartServices restarts a list of vehicle, monitor, or engine services.
func (d *Daemon) RestartServices(
	ctx context.Context,
	req *daemonpb.RestartServicesRequest,
) (*daemonpb.RestartServicesResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "RestartServices not implemented")
}

// InstallPackage installs a new package of plugins locally. The package is
// staged and takes effect on the next daemon restart.
func (d *Daemon) InstallPackage(
	ctx context.Context,
	req *daemonpb.InstallPackageRequest,
) (*daemonpb.InstallPackageResponse, error) {
	if err := d.installPackage(ctx, req.GetUrl(), req.GetTag()); err != nil {
		d.log.Error().Err(err).Str("url", req.GetUrl()).Msg("could not install package")
		return nil, err
	}
	return &daemonpb.InstallPackageResponse{}, nil
}

// RemovePackage removes a package identified by its URL. The removal takes
// effect on the next daemon restart.
func (d *Daemon) RemovePackage(
	ctx context.Context,
	req *daemonpb.RemovePackageRequest,
) (*daemonpb.RemovePackageResponse, error) {
	if err := d.removePackage(req.GetUrl()); err != nil {
		d.log.Error().Err(err).Str("url", req.GetUrl()).Msg("could not remove package")
		return nil, err
	}
	return &daemonpb.RemovePackageResponse{}, nil
}
