package daemon

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// RegisterOrchestrator is called by a daemon that has this daemon as its
// orchestrator. The stream opens with a handshake, where the registering daemon
// sends its services and this daemon answers with the remote compute service
// details and the engines it serves. After that, the stream is a heartbeat of
// empty requests, each answered with an empty response.
func (d *Daemon) RegisterOrchestrator(
	stream grpc.BidiStreamingServer[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse],
) error {
	// TODO: handshake, then heartbeat until the stream dies
	return status.Error(codes.Unimplemented, "RegisterOrchestrator is not implemented")
}

// Configure replaces the daemon config with the given TOML and restarts the
// daemon, running all services.
func (d *Daemon) Configure(
	ctx context.Context,
	req *daemonpb.ConfigureRequest,
) (*daemonpb.ConfigureResponse, error) {
	// TODO: write the config and trigger a restart
	return nil, status.Error(codes.Unimplemented, "Configure is not implemented")
}

// GetConfiguration returns the current config as TOML bytes.
func (d *Daemon) GetConfiguration(
	ctx context.Context,
	req *daemonpb.GetConfigurationRequest,
) (*daemonpb.GetConfigurationResponse, error) {
	// TODO: read the current config
	return nil, status.Error(codes.Unimplemented, "GetConfiguration is not implemented")
}

// ListServices lists all services from the config, whether they are running or
// stopped, along with why each couldn't be set up, failed to start, or exited.
// On an orchestrator, the services of every registered remote daemon are
// listed too, by their qualified names, "{daemon IP}.{name}"; a remote daemon
// that can't be reached is left out and listed as unavailable.
func (d *Daemon) ListServices(
	ctx context.Context,
	req *daemonpb.ListServicesRequest,
) (*daemonpb.ListServicesResponse, error) {
	// TODO: list local services, then merge in those of remote daemons
	return nil, status.Error(codes.Unimplemented, "ListServices is not implemented")
}

// RestartService restarts a target daemon service.
func (d *Daemon) RestartService(
	ctx context.Context,
	req *daemonpb.RestartServiceRequest,
) (*daemonpb.RestartServiceResponse, error) {
	// TODO: validate the targets and restart them
	return nil, status.Error(codes.Unimplemented, "RestartService is not implemented")
}

// Restart restarts the whole daemon and all of its services, including core
// services that have died. The config is reloaded and pending package changes
// are applied, like after a Configure call.
func (d *Daemon) Restart(
	ctx context.Context,
	req *daemonpb.RestartRequest,
) (*daemonpb.RestartResponse, error) {
	// TODO: trigger a restart
	return nil, status.Error(codes.Unimplemented, "Restart is not implemented")
}

// InstallPackage installs a package locally, indexing its plugins for future
// Configure calls.
func (d *Daemon) InstallPackage(
	ctx context.Context,
	req *daemonpb.InstallPackageRequest,
) (*daemonpb.InstallPackageResponse, error) {
	// TODO: download and index the package
	return nil, status.Error(codes.Unimplemented, "InstallPackage is not implemented")
}

// ListPackages lists all locally installed packages.
func (d *Daemon) ListPackages(
	ctx context.Context,
	req *daemonpb.ListPackagesRequest,
) (*daemonpb.ListPackagesResponse, error) {
	// TODO: list installed packages with their plugin tomls
	return nil, status.Error(codes.Unimplemented, "ListPackages is not implemented")
}

// RemovePackage removes the package identified by its uri.
func (d *Daemon) RemovePackage(
	ctx context.Context,
	req *daemonpb.RemovePackageRequest,
) (*daemonpb.RemovePackageResponse, error) {
	// TODO: remove the package
	return nil, status.Error(codes.Unimplemented, "RemovePackage is not implemented")
}

// populateServices creates service objects for all the services in the
// daemon config file, so that they can be sent to the orchestrator or
// children. Called only on startup.
func (d *Daemon) populateServices() error {
	d.srvMu.Lock()
	defer d.srvMu.Unlock()
	// Populate simulator (only placed in d.all, not in a category)
	simulator := &service{
		name:     d.qualify(SimulatorName),
		category: daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR,
		uri:      d.Config.Simulator.Package,
	}
	// Verify the simulator package exists
	_, err := util.GetPackageDirByCategoryAndName(
		SimulatorName,
		getPackageDir(d.Config.Simulator.Package),
	)
	if err != nil {
		d.log.Error().Err(err).
			Str("package", d.Config.Simulator.Package).
			Msg("simulator package not found")
		return err
	}
	d.all[simulator.name] = simulator
	// Populate services
	for _, service := range d.Config.Services {
		var mapToUse map[string]*service
		var serviceType daemonpb.ServiceCategory
		switch serivce.Type {
		case config.ServiceEngine:
			serviceType = daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE
			mapToUse = d.engines
		case config.ServiceVehicle:
			serviceType = daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE
			mapToUse = d.vehicles
		case config.ServiceExtra:
			serviceType = daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA
			mapToUse = d.extras
		}
		path, err := util.GetPackageDirByCategoryAndName(
			getDirectoryForCategory(serviceType),
			getPackageDir(service.Plugin.Package),
		)
		if err != nil && !service.Simulate {
			d.log.Error().Err(err).Str("package", service.Plugin.Package).
				Str("service", service.Name).
				Msg("package not found for service")
			return err
		}
		qualName := d.qualify(service.Name)
		name := sanitizePluginName(service.Plugin.Plugin)
		conf, err := config.ParsePluginConfigFromFilepath(filepath.Join(path, name))
		pkg := service.Plugin.Package
		if err != nil {
			return err
		}
		mapToUse[qualName] = &service{
			name:       qualName,
			category:   serviceType,
			uri:        pkg,
			pluginName: name,
			config:     conf,
			simulated:  service.Simulate,
		}
		d.all = mapToUse[qualName]
		if service.Simulate { // track simulated packages separately
			d.simulated = mapToUse[qualName]
		}
	}
	return nil
}

// startServices starts all the services in the daemon's config file. Called
// only on startup.
func (d *Daemon) startServices() error {
	d.srvMu.Lock()
	defer d.srvMu.Unlock()
	// Start each individual service
	for _, service := range d.all {
		err := d.startService(service)
		if err != nil {
			return err
		}
	}
	return nil
}

// startService starts a single daemon service. Must be called while holding the
// service lock.
func (d *Daemon) startService(s *service) error {
	if s.plugin != nil { // plugin already exists (restart case)
		if s.plugin.Running() { // if the plugin is running, cancel it
			s.cancel()
			s.conn.Close()
			s.Wait()
			d.log.Info().Str("service", s.name).Str("plugin", s.pluginName).
				Msg("stopped plugin for service")
		}

	} else { // plugin doesn't exist (fresh start case)
		dir, err := GetPluginDirByCategoryAndName(
			getDirectoryForCategory(s.category),
			s.name,
		)
		if err != nil {
			return err
		}
		logFile, err := GetLogForName(s.name)
		if err != nil {
			return err
		}
		// TODO: initialize models/ and files/
		options := []plugin.PluginOption{
			plugin.WithLogger(
				d.log.With().Str("service", s.name).Str("plugin".s.pluginName).Logger(),
			),
			plugin.WithParentDir(dir),
			plugin.WithProcessOutputStream(os.Create(logFile)),
		}
		switch s.category {
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR:
			options = append(
				options,
				plugin.WithoutListener(), plugin.WithoutClient(),
			)
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:
			options = append(
				options,
				WithReadOnlyFiles([]string{}), // models and files
			)
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:
			options = append(
				options,
				WithFiles([]string{}), // mission dir for vehicle
			)
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA:
		default:
			return fmt.Errorf("unrecognized service category for %s", s.name)
		}
		var p plugin.Plugin
		switch {
		case s.config.Isolate == SandboxName: // sandbox
		case s.config.Isolate != "": // container
		default: // simulated or process
			// Simulated services need shim plugins
			if s.simlated {
				p = plugin.NewShimPlugin()
			} else {
				p = plugin.NewBasePlugin()
			}
		}
	}
	ctx, cancel = context.WithCancel(d.ctx)
	s.cancel = cancel
	s.ln, s.conn, err = s.plugin.Start(ctx)
	if err != nil {
		d.log.Error().Err(err).Str("plugin", s.pluginName).
			Msg("failed to start plugin")
		return err
	}
	d.log.Info().Str("service", s.name).Str("plugin", s.pluginName).
		Msg("started plugin for service")
	// This serve will clean itself up when the plugin stops and tears down
	// the listener
	if s.ln != nil {
		go d.server.Serve(s.ln)
	}
}

// getPackageDir gets a package directory name from a package uri.
func getPackageDir(uri string) string {
	return strings.NewReplacer("/", "_", ".", "_", ":", "_").Replace(uri)
}

// sanitizePluginName checks for a .plugin.toml suffix, and if it is not present,
// it adds one.
func sanitizePluginName(name string) string {
	if strings.HasSuffix(name) {
		return name
	} else {
		return name + PluginFileSuffix
	}
}

// getDirectoryForCategory gets the correct directory name for a daemon service
// category.
func getDirectoryForCategory(category daemonpb.ServiceCategory) string {
	switch serivce.Type {
	case SimulatorName:
		return SimulatorDir
	case config.ServiceEngine:
		return EngineDir
	case config.ServiceVehicle:
		return VehicleDir
	case config.ServiceExtra:
		return ExtraDir
	default:
		return UnknownDir
	}
}

// commitPackages writes packages in the .pending directory into the main
// package directory. This is called on every daemon restart to initialize
// plugins installed during the daemon's last run.
func commitPackages() error {
	source, err := util.GetPendingDir()
	if err != nil {
		return nil
	}
	dest, err := util.GetPackageDir()
	if err != nil {
		return nil
	}
	return os.CopyFS(dest, os.DirFS(source))
}
