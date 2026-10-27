package daemon

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"github.com/cmusatyalab/steeleagle/v4/core/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// RegisterOrchestrator is called by a daemon that has this daemon as its
// orchestrator. The stream opens with a handshake, where the registering
// daemon sends its services, which must all be qualified with its IP, and this
// daemon answers with its own. The registering daemon and its services become
// routes to it until the stream ends. After that, the stream is a heartbeat of
// empty requests, each answered with an empty response.
func (d *Daemon) RegisterOrchestrator(
	stream grpc.BidiStreamingServer[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse],
) error {
	return d.serveRegistration(stream)
}

// GetConnectionStatus returns whether this daemon is connected to its
// orchestrator. A daemon without an orchestrator is always connected.
func (d *Daemon) GetConnectionStatus(
	ctx context.Context,
	req *daemonpb.GetConnectionStatusRequest,
) (*daemonpb.GetConnectionStatusResponse, error) {
	return daemonpb.GetConnectionStatusResponse_builder{
		Connected: d.Config.Daemon.Orchestrator == "" || d.connected.Load(),
	}.Build(), nil
}

// Configure replaces the daemon config with the given TOML and restarts the
// daemon, running all services. The config is validated first, and written
// atomically, so that a bad config never replaces a good one.
func (d *Daemon) Configure(
	ctx context.Context,
	req *daemonpb.ConfigureRequest,
) (*daemonpb.ConfigureResponse, error) {
	content := []byte(req.GetConfigToml())
	if _, err := config.ParseDaemonConfigFromBytes(content); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid config: %v", err)
	}
	tmp, err := os.CreateTemp(filepath.Dir(d.configPath), ".config-*.toml")
	if err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't write config: %v", err)
	}
	defer os.Remove(tmp.Name())
	_, err = tmp.Write(content)
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err == nil {
		err = os.Rename(tmp.Name(), d.configPath)
	}
	if err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't write config: %v", err)
	}
	d.log.Info().Str("path", d.configPath).Msg("config replaced, restarting")
	d.restarting.Store(true)
	d.cancel()
	return &daemonpb.ConfigureResponse{}, nil
}

// GetConfiguration returns the current config as TOML bytes.
func (d *Daemon) GetConfiguration(
	ctx context.Context,
	req *daemonpb.GetConfigurationRequest,
) (*daemonpb.GetConfigurationResponse, error) {
	content, err := os.ReadFile(d.configPath)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't read config: %v", err)
	}
	return daemonpb.GetConfigurationResponse_builder{ConfigToml: content}.Build(), nil
}

// ListServices lists all services from the config, whether they are running or
// stopped. On an orchestrator, the services of every registered remote daemon
// are listed too, by their qualified names, "{daemon IP}.{name}"; a remote
// daemon that can't be reached is left out and listed as unavailable. If the
// daemon failed to start its services, it returns that error instead.
func (d *Daemon) ListServices(
	ctx context.Context,
	req *daemonpb.ListServicesRequest,
) (*daemonpb.ListServicesResponse, error) {
	if d.err != nil {
		return nil, status.Errorf(codes.FailedPrecondition, "daemon failed to start services: %v", d.err)
	}
	d.svcMu.RLock()
	services, err := d.serviceProtos()
	d.svcMu.RUnlock()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't encode services: %v", err)
	}
	var unavailable []*daemonpb.Unavailable
	for _, child := range d.listRemotes() {
		// The child routes its own IP to its own services
		cctx, cancel := context.WithTimeout(router.Embed(ctx, child.ip), Deadline)
		resp, err := daemonpb.NewDaemonServiceClient(child.conn).
			ListServices(cctx, &daemonpb.ListServicesRequest{})
		cancel()
		if err != nil {
			unavailable = append(unavailable, daemonpb.Unavailable_builder{
				Ip:       child.ip,
				Hostname: child.hostname,
				Reason:   err.Error(),
			}.Build())
			continue
		}
		services = append(services, resp.GetServices()...)
		unavailable = append(unavailable, resp.GetUnavailable()...)
	}
	return daemonpb.ListServicesResponse_builder{
		Services:    services,
		Unavailable: unavailable,
	}.Build(), nil
}

// RestartService restarts a target daemon service. A service on a registered
// remote daemon is restarted by that daemon. If the daemon failed to start
// its services, it returns that error instead.
func (d *Daemon) RestartService(
	ctx context.Context,
	req *daemonpb.RestartServiceRequest,
) (*daemonpb.RestartServiceResponse, error) {
	if d.err != nil {
		return nil, status.Errorf(codes.FailedPrecondition, "daemon failed to start services: %v", d.err)
	}
	name := req.GetServiceNames()
	if child := d.remoteFor(name); child != nil {
		ctx, cancel := context.WithTimeout(router.Embed(ctx, child.ip), RestartDeadline)
		defer cancel()
		return daemonpb.NewDaemonServiceClient(child.conn).RestartService(ctx, req)
	}
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	s, ok := d.lookup[name]
	if !ok {
		return nil, status.Errorf(codes.NotFound, "no service %q", name)
	}
	if err := d.startService(s); err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't restart service %q: %v", name, err)
	}
	return &daemonpb.RestartServiceResponse{}, nil
}

// Restart restarts the whole daemon and all of its services, including core
// services that have died. The config is reloaded and pending package changes
// are applied, like after a Configure call.
func (d *Daemon) Restart(
	ctx context.Context,
	req *daemonpb.RestartRequest,
) (*daemonpb.RestartResponse, error) {
	d.log.Info().Msg("restart requested")
	d.restarting.Store(true)
	d.cancel()
	return &daemonpb.RestartResponse{}, nil
}

// InstallPackage installs a package locally, indexing its plugins for future
// Configure calls. The package takes effect on the next daemon restart.
func (d *Daemon) InstallPackage(
	ctx context.Context,
	req *daemonpb.InstallPackageRequest,
) (*daemonpb.InstallPackageResponse, error) {
	if req.GetUri() == "" {
		return nil, status.Error(codes.InvalidArgument, "no package uri")
	}
	d.pkgMu.Lock()
	defer d.pkgMu.Unlock()
	if err := installPackage(req.GetUri()); err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't install package %s: %v", req.GetUri(), err)
	}
	d.log.Info().Str("package", req.GetUri()).Msg("package installed, pending restart")
	return &daemonpb.InstallPackageResponse{}, nil
}

// ListPackages lists all locally installed packages, including installs and
// removals pending the next restart.
func (d *Daemon) ListPackages(
	ctx context.Context,
	req *daemonpb.ListPackagesRequest,
) (*daemonpb.ListPackagesResponse, error) {
	d.pkgMu.RLock()
	defer d.pkgMu.RUnlock()
	packages, err := listPackages()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't list packages: %v", err)
	}
	return daemonpb.ListPackagesResponse_builder{Packages: packages}.Build(), nil
}

// RemovePackage removes the package identified by its uri. The removal takes
// effect on the next daemon restart.
func (d *Daemon) RemovePackage(
	ctx context.Context,
	req *daemonpb.RemovePackageRequest,
) (*daemonpb.RemovePackageResponse, error) {
	d.pkgMu.Lock()
	defer d.pkgMu.Unlock()
	if err := removePackage(req.GetUri()); errors.Is(err, fs.ErrNotExist) {
		return nil, status.Errorf(codes.NotFound, "no package %s", req.GetUri())
	} else if err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't remove package %s: %v", req.GetUri(), err)
	}
	d.log.Info().Str("package", req.GetUri()).Msg("package removed, pending restart")
	return &daemonpb.RemovePackageResponse{}, nil
}

// populateServices creates service objects for all the services in the
// daemon config file, so that they can be sent to the orchestrator or
// children. Called only on startup.
func (d *Daemon) populateServices() error {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	// Populate simulator (if a plugin is specified)
	var simPath string
	if d.Config.Simulator.Package != "" {
		// Verify the simulator package exists
		var err error
		simPath, err = util.GetPackageDirByName(getPackageDir(d.Config.Simulator.Package))
		if err != nil {
			d.log.Error().Err(err).
				Str("package", d.Config.Simulator.Package).
				Msg("simulator package not found")
			return err
		}
		args, err := encodeArgs(d.Config.Simulator.Args)
		if err != nil {
			return fmt.Errorf("couldn't encode simulator args: %w", err)
		}
		// The simulator is run with its args, but no plugin name
		simulator := &daemonService{
			name:      d.qualify(SimulatorName),
			category:  daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR,
			uri:       d.Config.Simulator.Package,
			path:      simPath,
			args:      args,
			isolation: daemonpb.Isolation_ISOLATION_PROCESS,
			local:     true,
		}
		d.lookup[simulator.name] = simulator
		d.services = append(d.services, simulator)
	}
	// Populate services
	for _, svc := range d.Config.Services {
		var serviceType daemonpb.ServiceCategory
		switch svc.Type {
		case config.ServiceEngine:
			serviceType = daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE
		case config.ServiceVehicle:
			serviceType = daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE
		case config.ServiceExtra:
			serviceType = daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA
		}
		s := &daemonService{
			name:      d.qualify(svc.Name),
			category:  serviceType,
			isolation: daemonpb.Isolation_ISOLATION_PROCESS,
			auth:      listener.ToCode(string(svc.AuthLevel())),
			local:     true,
			simulated: svc.Simulate,
		}
		if svc.Simulate && simPath == "" {
			err := fmt.Errorf("service %q is simulated, but no simulator is configured", svc.Name)
			d.log.Error().Err(err).Msg("simulator not found for service")
			return err
		}
		if err := d.setPlugin(s, svc.Plugin); err != nil {
			d.log.Error().Err(err).Str("package", svc.Plugin.Package).
				Str("service", svc.Name).Msg("couldn't set up plugin for service")
			return fmt.Errorf("service %s: %w", s.name, err)
		}
		if svc.Simulate {
			// Simulated services are run by the simulator, which gets their
			// config through its args, so their plugin's args and isolation
			// are ignored
			s.args = "{}"
			s.isolation = daemonpb.Isolation_ISOLATION_PROCESS
			s.container = ""
		}
		d.lookup[s.name] = s
		d.services = append(d.services, s)
	}
	return nil
}

// startServices starts all the services in the daemon's config file. Called
// only on startup.
func (d *Daemon) startServices() error {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	// Start each individual service
	for _, service := range d.services {
		err := d.startService(service)
		if err != nil {
			return fmt.Errorf(
				"failed to start service %s: %v",
				service.name,
				err,
			)
		}
	}
	return nil
}

// startService starts a single daemon service. The caller must hold svcMu.
func (d *Daemon) startService(s *daemonService) error {
	if s == nil {
		return fmt.Errorf("cannot start nil service")
	}
	var plug *daemonPlugin
	var ok bool
	if plug, ok = d.plugins[s.name]; ok { // plugin already exists (restart case)
		stopPluginOrVehicle(plug)
		if plug.vehicle == nil {
			d.log.Info().Str("service", s.name).Str("plugin", s.pluginName).
				Msg("stopped plugin for service")
		} else {
			d.log.Info().Str("vehicle", s.name).Msg("stopped vehicle")
		}
	} else { // plugin doesn't exist (fresh start case)
		plug = &daemonPlugin{}
		// Initialize or get directories
		dir, err := util.GetPluginDirByName(s.name)
		if err != nil {
			d.log.Error().Err(err).Str("service", s.name).
				Msg("couldn't open plugin directory")
			return err
		}
		logFile, err := util.GetLogByName(s.name)
		if err != nil {
			d.log.Error().Err(err).Str("service", s.name).
				Msg("couldn't open log directory")
			return err
		}
		// Construct base options
		logStream, err := os.Create(logFile)
		if err != nil {
			d.log.Error().Err(err).Str("service", s.name).
				Msg("couldn't open log stream")
			return err
		}
		plug.logStream = logStream
		defer func() {
			if _, ok := d.plugins[s.name]; !ok {
				logStream.Close() // cleanup the log if the plugin failed
			}
		}()
		options := []plugin.PluginOption{
			plugin.WithLogger(
				d.log.With().Str("service", s.name).Str("plugin", s.pluginName).Logger(),
			),
			plugin.WithParentDir(dir),
			// The parent directory is the service's own, so the run directory
			// needn't be unique, and is kept short since sockets are made in it
			plugin.WithName(PluginRunDirName),
			plugin.WithPath(s.path),
			plugin.WithProcessOutputStream(plug.logStream),
			plugin.WithAuthCode(s.auth),
			plugin.WithEnvironment(PluginArgsEnv, s.args),
			plugin.WithEnvironment(PluginNameEnv, s.pluginName), // this will be empty for the simulator
		}
		switch s.category {
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR: // sim options
			options = append(
				options,
				plugin.WithoutListener(), plugin.WithoutClient(),
			)
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE: // engine options
			models, err := util.GetModelDir()
			if err != nil {
				d.log.Error().Err(err).Str("service", s.name).
					Msg("couldn't open model directory")
				return err
			}
			files, err := util.GetFileDir()
			if err != nil {
				d.log.Error().Err(err).Str("service", s.name).
					Msg("couldn't open file directory")
				return err
			}
			options = append(
				options,
				plugin.WithFiles([]string{models, files}),
				plugin.WithEnvironment(ModelNameEnv, models),
				plugin.WithEnvironment(FileNameEnv, files),
				// The compute server serves the engine under its service name
				plugin.WithEnvironment(IceoryxServiceEnv, s.name),
			)
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE: // vehicle options
			options = append(
				options, plugin.WithoutListener(),
			)
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA: // extra options
		default:
		}
		var p plugin.Plugin
		switch s.isolation {
		case daemonpb.Isolation_ISOLATION_SANDBOX: // sandbox
			p, err = plugin.NewSandboxPlugin(options...)
		case daemonpb.Isolation_ISOLATION_CONTAINER: // container
			p, err = plugin.NewContainerPlugin(s.container, options...)
		default: // simulated or process
			// Simulated services need shim plugins
			if s.simulated {
				var sim string
				sim, err = util.GetSimPluginDirByName(s.name)
				if err != nil {
					d.log.Error().Err(err).Str("service", s.name).
						Msg("couldn't open simulated plugin directory")
					return err
				}
				p, err = plugin.NewShimPlugin(
					filepath.Join(sim, ShimClientSock),
					filepath.Join(sim, ShimListenSock),
				)
			} else {
				p, err = plugin.NewBasePlugin(options...)
			}
		}
		if err != nil {
			d.log.Error().Err(err).Str("service", s.name).Str("plugin", s.pluginName).
				Msg("failed to create plugin")
			return err
		}
		// Create the vehicle
		if s.category == daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE {
			mission, err := util.GetVehicleMissionDirByName(s.name)
			if err != nil {
				d.log.Error().Err(err).Str("vehicle", s.name).
					Msg("couldn't open mission directory")
				return err
			}
			vehicleOptions := []vehicle.VehicleOption{
				vehicle.WithName(s.name),
				vehicle.WithAuthCode(s.auth),
				vehicle.WithMissionDir(mission),
				vehicle.WithLogger(
					d.log.With().Str("vehicle", s.name).Logger().Output(plug.logStream),
				),
			}
			d.orchMu.RLock()
			orch := d.orch
			d.orchMu.RUnlock()
			if orch != nil {
				vehicleOptions = append(
					vehicleOptions,
					vehicle.WithLocalAndRemoteCompute(
						d.Hostname,
						net.JoinHostPort(orch.ip, strconv.Itoa(orch.lcsPort)),
						orch.cert,
						getVehicleEngineMap(d.services, orch.services),
					),
				)
			} else {
				vehicleOptions = append(
					vehicleOptions,
					vehicle.WithLocalCompute(
						d.Hostname,
						getVehicleEngineMap(d.services, nil),
					),
				)
			}
			plug.vehicle, err = vehicle.NewVehicle(p, s.config, vehicleOptions...)
			if err != nil {
				d.log.Error().Err(err).Str("vehicle", s.name).Msg("failed to create vehicle")
				return err
			}
		}
		// Add the plugin to the map
		plug.plugin = p
		d.plugins[s.name] = plug
	}
	ctx, cancel := context.WithCancel(d.ctx)
	plug.cancel = cancel
	var err error
	if plug.vehicle == nil {
		plug.ln, plug.conn, err = plug.plugin.Start(ctx)
		if err != nil {
			d.log.Error().Err(err).Str("service", s.name).Str("plugin", s.pluginName).
				Msg("failed to start plugin")
			return err
		}
		// This serve will clean itself up when the plugin stops and tears down
		// the listener
		if plug.ln != nil {
			go d.relay.Serve(plug.ln)
		}
		d.log.Info().Str("service", s.name).Str("plugin", s.pluginName).
			Msg("started plugin for service")
	} else {
		plug.ln, plug.conn, err = plug.vehicle.Start(ctx)
		if err != nil {
			d.log.Error().Err(err).Str("vehicle", s.name).
				Msg("failed to start vehicle")
			return err
		}
		// Like a plugin's, this serve cleans itself up when the vehicle stops
		// and tears down the listener
		if plug.ln != nil {
			go d.relay.Serve(plug.ln)
		}
		d.log.Info().Str("vehicle", s.name).Msg("started vehicle")
	}
	// Add routing for this service
	d.router.AddHeaderRoute(s.name, plug.conn)
	return nil
}

// stopPluginOrVehicle stops the current run of a plugin or vehicle, so that it
// can be started again. The caller must hold svcMu.
func stopPluginOrVehicle(plug *daemonPlugin) {
	if plug.cancel != nil {
		plug.cancel()
	}
	// A vehicle's run may still be stopping after its driver exited, so it is
	// always waited for; it waits for its driver
	if plug.vehicle != nil {
		plug.vehicle.Wait()
	} else if plug.plugin.Running() {
		plug.plugin.Wait()
	}
	if plug.conn != nil {
		plug.conn.Close()
		plug.conn = nil
	}
}

// setPlugin sets the plugin of a service from its plugin field in the daemon
// config, reading its plugin file from its installed package.
func (d *Daemon) setPlugin(s *daemonService, p config.PluginField) error {
	path, err := util.GetPackageDirByName(getPackageDir(p.Package))
	if err != nil {
		return err
	}
	name := strings.TrimSuffix(p.Plugin, PluginFileSuffix)
	// The plugin file must be at the root of its package
	if name == "" || name == "." || name == ".." || filepath.Base(name) != name {
		return fmt.Errorf("invalid plugin name %q", p.Plugin)
	}
	conf, err := config.ParsePluginConfigFromFilepath(filepath.Join(path, name+PluginFileSuffix))
	if err != nil {
		return err
	}
	args, err := encodeArgs(p.Args)
	if err != nil {
		return fmt.Errorf("couldn't encode args: %w", err)
	}
	switch {
	case p.Isolation == config.IsolationSandbox:
		s.isolation = daemonpb.Isolation_ISOLATION_SANDBOX
	case p.Isolation != "":
		s.isolation = daemonpb.Isolation_ISOLATION_CONTAINER
		s.container = p.Isolation
	}
	s.uri, s.pluginName, s.path, s.args, s.config = p.Package, name, path, args, conf
	return nil
}

// encodeArgs encodes plugin args as a JSON object, which is empty if there
// are none.
func encodeArgs(args map[string]any) (string, error) {
	if args == nil {
		args = map[string]any{}
	}
	b, err := json.Marshal(args)
	return string(b), err
}

// closePlugin stops a plugin or vehicle and releases what it holds across
// runs, like its log stream. The caller must hold svcMu.
func closePlugin(plug *daemonPlugin) {
	stopPluginOrVehicle(plug)
	if closer, ok := plug.logStream.(io.Closer); ok {
		closer.Close()
		plug.logStream = nil
	}
}

// getVehicleEngineMap gets a map from all available engines to their configs.
func getVehicleEngineMap(locals []*daemonService, remotes []*daemonService) vehicle.EngineMap {
	out := make(vehicle.EngineMap)
	for _, service := range locals {
		if service.category != daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE {
			continue
		}
		out[service.name] = &vehicle.EngineInfo{
			Config: service.config,
			Local:  true,
		}
	}
	for _, service := range remotes {
		if service.category != daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE {
			continue
		}
		out[service.name] = &vehicle.EngineInfo{
			Config: service.config,
			Local:  false,
		}
	}
	return out
}

// getPackageDir gets a package directory name from a package uri.
func getPackageDir(uri string) string {
	return strings.NewReplacer("/", "_", ".", "_", ":", "_").Replace(uri)
}
