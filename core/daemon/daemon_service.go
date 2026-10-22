package daemon

import (
	"context"
	"os"
	"path/filepath"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/durationpb"
)

// RegisterOrchestrator is called by a daemon that has this daemon as its
// orchestrator, and stays open as a heartbeat. Its vehicles become addressable
// through this daemon's router, and it gets back the cert and port of this
// daemon's local compute service, along with the plugin toml of each engine it
// serves, which become remote engines for its vehicles.
func (d *Daemon) RegisterOrchestrator(
	stream grpc.BidiStreamingServer[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse],
) error {
	if err := d.serveRegistration(stream); err != nil {
		d.log.Error().Err(err).Msg("registration stream failed")
		return err
	}
	return nil
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
	d.log.Info().Str("path", d.configPath).Msg("daemon config replaced")
	d.stopForRestart()
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
	// Only services that were set up have a plugin toml
	tomls := make(map[string][]byte)
	d.eachService(func(s *serviceInfo) {
		if s.toml != nil {
			tomls[categories[s.category].name+"/"+s.name] = s.toml
		}
	})
	return daemonpb.GetConfigurationResponse_builder{ConfigToml: content, PluginTomls: tomls}.Build(), nil
}

// ListServices lists all services from the config, whether they are running
// or stopped, followed by the services of every registered remote daemon on an
// orchestrator. Services are listed by their qualified names, so those of
// different daemons never collide.
func (d *Daemon) ListServices(
	ctx context.Context,
	req *daemonpb.ListServicesRequest,
) (*daemonpb.ListServicesResponse, error) {
	var services []*daemonpb.ActiveService
	d.eachService(func(s *serviceInfo) {
		running := s.running()
		var uptime *durationpb.Duration
		if running {
			uptime = durationpb.New(time.Since(s.started))
		}
		services = append(services, daemonpb.ActiveService_builder{
			Srv:     daemonpb.Service_builder{Name: s.name, Category: s.category}.Build(),
			Plugin:  s.pluginName,
			Url:     s.url,
			Running: running,
			Uptime:  uptime,
			Error:   s.errorString(),
		}.Build())
	})
	remote, unavailable := d.listRemoteServices(ctx)
	services = append(services, remote...)
	return daemonpb.ListServicesResponse_builder{Services: services, Unavailable: unavailable}.Build(), nil
}

// RestartServices restarts a list of vehicle, monitor, or engine services. A
// bad entry rejects the whole request before any service is touched.
func (d *Daemon) RestartServices(
	ctx context.Context,
	req *daemonpb.RestartServicesRequest,
) (*daemonpb.RestartServicesResponse, error) {
	targets, err := d.restartTargets(req.GetServices())
	if err != nil {
		return nil, err
	}
	d.stopServices(targets)
	if err := d.startServices(targets); err != nil {
		d.log.Error().Err(err).Msg("could not start services")
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &daemonpb.RestartServicesResponse{}, nil
}

// restartTargets looks up the services of a restart request, which must all
// be set up and of a restartable category.
func (d *Daemon) restartTargets(services []*daemonpb.Service) ([]*serviceInfo, error) {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	var targets []*serviceInfo
	for _, s := range services {
		if !categories[s.GetCategory()].restartable {
			return nil, status.Errorf(codes.InvalidArgument,
				"service %q has category %s, only vehicles, monitors and engines can be restarted; use Configure for the rest",
				s.GetName(), s.GetCategory())
		}
		target, err := d.lookupService(s.GetCategory(), s.GetName())
		if err != nil {
			return nil, err
		}
		targets = append(targets, target)
	}
	return targets, nil
}

// Restart stops the daemon, closing all of its services, so that it is
// restarted with all of them by its supervisor.
func (d *Daemon) Restart(
	ctx context.Context,
	req *daemonpb.RestartRequest,
) (*daemonpb.RestartResponse, error) {
	d.log.Info().Msg("restart requested")
	d.stopForRestart()
	return &daemonpb.RestartResponse{}, nil
}

// stopForRestart stops the daemon, so that Run returns ErrRestart once
// everything is closed. Stopping is graceful, so the calling RPC returns
// before the relay shuts down.
func (d *Daemon) stopForRestart() {
	d.log.Info().Msg("stopping for restart")
	d.restart.Store(true)
	d.cancel()
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
	cfg, err := config.ParseDaemonConfigFromBytes(content)
	if err != nil {
		return status.Errorf(codes.InvalidArgument, "invalid daemon config: %v", err)
	}
	if err := cfg.ValidateServices(); err != nil {
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
