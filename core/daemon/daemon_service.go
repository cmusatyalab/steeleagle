package daemon

import (
	"context"
	"os"
	"path/filepath"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// RegisterOrchestrator is called by a daemon that has this daemon as its
// orchestrator. Its vehicles become addressable through this daemon's router,
// and it gets back the cert and port of this daemon's local compute service.
func (d *Daemon) RegisterOrchestrator(
	ctx context.Context,
	req *daemonpb.RegisterOrchestratorRequest,
) (*daemonpb.RegisterOrchestratorResponse, error) {
	cert, err := d.registerOrchestrator(ctx, req.GetVehicles(), req.GetPort())
	if err != nil {
		d.log.Error().Err(err).Strs("vehicles", req.GetVehicles()).Msg("could not register as orchestrator")
		return nil, err
	}
	return daemonpb.RegisterOrchestratorResponse_builder{
		Cert: cert,
		Port: int32(d.Config.Daemon.Lcs),
	}.Build(), nil
}

// Configure replaces the config.toml on disk and stops the daemon, so that it
// is restarted with the new config. The current config is already loaded, so
// overwriting it doesn't affect the running daemon.
func (d *Daemon) Configure(
	ctx context.Context,
	req *daemonpb.ConfigureRequest,
) (*daemonpb.ConfigureResponse, error) {
	if err := d.writeConfig([]byte(req.GetConfigToml())); err != nil {
		d.log.Error().Err(err).Str("path", d.configPath).Msg("could not write daemon config")
		return nil, err
	}
	// Stopping is graceful, so this call returns before the relay shuts down
	d.log.Info().Str("path", d.configPath).Msg("daemon config replaced, stopping")
	d.cancel()
	return &daemonpb.ConfigureResponse{}, nil
}

// GetConfiguration returns the current config.toml as bytes.
func (d *Daemon) GetConfiguration(
	ctx context.Context,
	req *daemonpb.GetConfigurationRequest,
) (*daemonpb.GetConfigurationResponse, error) {
	content, err := os.ReadFile(d.configPath)
	if err != nil {
		d.log.Error().Err(err).Str("path", d.configPath).Msg("could not read daemon config")
		return nil, status.Error(codes.Internal, err.Error())
	}
	return daemonpb.GetConfigurationResponse_builder{ConfigToml: content, PluginTomls: d.pluginTomls()}.Build(), nil
}

// ListServices lists all services from the config, whether they are running
// or stopped.
func (d *Daemon) ListServices(
	ctx context.Context,
	req *daemonpb.ListServicesRequest,
) (*daemonpb.ListServicesResponse, error) {
	return daemonpb.ListServicesResponse_builder{Services: d.listServices()}.Build(), nil
}

// RestartServices restarts a list of vehicle, monitor, or engine services.
func (d *Daemon) RestartServices(
	ctx context.Context,
	req *daemonpb.RestartServicesRequest,
) (*daemonpb.RestartServicesResponse, error) {
	targets, err := d.controllableServices(req.GetServices())
	if err != nil {
		return nil, err
	}
	if err := d.stopServices(targets); err != nil {
		d.log.Error().Err(err).Msg("could not stop services")
		return nil, status.Error(codes.Internal, err.Error())
	}
	if err := d.startServices(targets); err != nil {
		d.log.Error().Err(err).Msg("could not start services")
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &daemonpb.RestartServicesResponse{}, nil
}

// Restart stops the daemon, so that it is restarted with all of its services.
// Stopping is graceful, so this call returns before the relay shuts down.
func (d *Daemon) Restart(
	ctx context.Context,
	req *daemonpb.RestartRequest,
) (*daemonpb.RestartResponse, error) {
	d.log.Info().Msg("restart requested, stopping")
	d.cancel()
	return &daemonpb.RestartResponse{}, nil
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

// ListPackages lists the installed packages and the plugins in each, including
// installs and removals pending the next daemon restart.
func (d *Daemon) ListPackages(
	ctx context.Context,
	req *daemonpb.ListPackagesRequest,
) (*daemonpb.ListPackagesResponse, error) {
	packages, err := d.listPackages()
	if err != nil {
		d.log.Error().Err(err).Msg("could not list packages")
		return nil, err
	}
	return daemonpb.ListPackagesResponse_builder{Packages: packages}.Build(), nil
}

// writeConfig validates a config.toml and atomically replaces the one on disk
// with it, so that an invalid or partially written config never prevents the
// daemon from starting.
func (d *Daemon) writeConfig(content []byte) error {
	if _, err := config.ParseDaemonConfigFromBytes(content); err != nil {
		return status.Errorf(codes.InvalidArgument, "invalid daemon config: %v", err)
	}
	tmp, err := os.CreateTemp(filepath.Dir(d.configPath), "."+ConfigFileName+"-*")
	if err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	defer os.Remove(tmp.Name())
	if _, err := tmp.Write(content); err != nil {
		tmp.Close()
		return status.Error(codes.Internal, err.Error())
	}
	if err := tmp.Close(); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	if err := os.Chmod(tmp.Name(), 0644); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	if err := os.Rename(tmp.Name(), d.configPath); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	return nil
}
