package daemon

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/durationpb"
)

// categoryInfo describes how the services of a category are run.
type categoryInfo struct {
	pluginType string            // required plugin type in the .plugin.toml
	dir        string            // runtime directory for the category's plugins
	code       listener.AuthCode // AuthCode for calls from the plugin to the daemon
}

// gatherServices reads the services used by the config into d.services
// without starting them. A service that can't be set up, like one whose
// package isn't installed, is kept as broken with its error, so that it is
// listed but never started, and is reported in the returned error, so that the
// rest of the config can still run.
func (d *Daemon) gatherServices() error {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	d.services = make(map[daemonpb.ServiceCategory][]*serviceInfo)
	var errs []error
	add := func(name string, category daemonpb.ServiceCategory, field config.PluginField) {
		s, err := d.newService(name, category, field)
		if err != nil {
			errs = append(errs, fmt.Errorf("%s %q: %w", categories[category].pluginType, name, err))
			s = &serviceInfo{name: name, category: category, pluginName: field.Plugin, url: field.Package, err: err}
			if u, err := parsePackageUrl(field.Package); err == nil {
				s.url = u.url
			}
		}
		d.services[category] = append(d.services[category], s)
	}

	c := d.Config
	if c.Simulator.Name != "" {
		add(c.Simulator.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR, c.Simulator.Plugin)
	}
	for _, s := range c.Engines {
		add(s.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE, s.Plugin)
	}
	for _, v := range c.Vehicles {
		if v.Simulate {
			// Running the real driver in place of a simulated vehicle could fly
			// real hardware, so a simulated vehicle is never started
			err := fmt.Errorf("simulated vehicles are not supported yet")
			errs = append(errs, fmt.Errorf("vehicle %q: %w", v.Name, err))
			d.services[daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE] = append(
				d.services[daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE],
				&serviceInfo{name: v.Name, category: daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE,
					pluginName: v.Plugin.Plugin, url: v.Plugin.Package, err: err})
			continue
		}
		add(v.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE, v.Plugin)
	}
	for _, s := range c.Commanders {
		add(s.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_COMMANDER, s.Plugin)
	}
	for _, s := range c.Monitors {
		add(s.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR, s.Plugin)
	}
	for _, s := range c.Extras {
		add(s.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA, s.Plugin)
	}
	return errors.Join(errs...)
}

// newService finds the plugin for a service in its package and creates the
// plugin, ready to start. The caller must hold svcMu.
func (d *Daemon) newService(
	name string,
	category daemonpb.ServiceCategory,
	field config.PluginField,
) (*serviceInfo, error) {
	cat := categories[category]
	if name == "" {
		return nil, fmt.Errorf("service has no name")
	}
	if d.findService(category, name) != nil {
		return nil, fmt.Errorf("duplicate service name")
	}
	u, err := parsePackageUrl(field.Package)
	if err != nil {
		return nil, err
	}
	dir := filepath.Join(d.PkgDir, u.name)
	content, err := os.ReadFile(filepath.Join(dir, field.Plugin+PluginFileSuffix))
	if err != nil {
		return nil, fmt.Errorf("could not read plugin %q from %s: %w", field.Plugin, u.url, err)
	}
	cfg, err := config.ParsePluginConfigFromBytes(content)
	if err != nil {
		return nil, fmt.Errorf("could not read plugin %q from %s: %w", field.Plugin, u.url, err)
	}
	if cfg.Plugin.Type != cat.pluginType {
		return nil, fmt.Errorf("plugin %q is a %q plugin, not %q", field.Plugin, cfg.Plugin.Type, cat.pluginType)
	}
	args := field.Args
	if args == nil {
		args = map[string]any{}
	}
	argsJson, err := json.Marshal(args)
	if err != nil {
		return nil, fmt.Errorf("could not encode plugin args: %w", err)
	}

	options := []plugin.PluginOption{
		plugin.WithName(name),
		plugin.WithPath(dir),
		plugin.WithLogger(d.log),
		plugin.WithEnvironment(PluginNameEnv, field.Plugin),
		plugin.WithEnvironment(PluginArgsEnv, string(argsJson)),
	}
	if d.pluginOut != nil {
		options = append(options, plugin.WithProcessOutputStream(d.pluginOut))
	}
	switch category {
	case daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:
		// Engines serve over iceoryx, so the daemon has no client connection to
		// them, but they can call the daemon through their listener. They can
		// read, but not change, the models transferred to the daemon
		models, err := util.GetModelDir()
		if err != nil {
			return nil, fmt.Errorf("could not get model directory: %w", err)
		}
		options = append(options, plugin.WithoutClient(), plugin.WithAuthCode(cat.code),
			plugin.WithParentDir(cat.dir), plugin.WithEnvironment(IceoryxServiceEnv, name),
			plugin.WithReadOnlyFiles([]string{models}))
	case daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:
		// Drivers are pure servers for their vehicle, and run within its
		// runtime directory
		if cfg.Driver == nil {
			return nil, fmt.Errorf("plugin %q has no driver cap", field.Plugin)
		}
		options = append(options, plugin.WithoutListener(),
			plugin.WithParentDir(filepath.Join(cat.dir, name)))
	default:
		options = append(options, plugin.WithoutClient(),
			plugin.WithAuthCode(cat.code), plugin.WithParentDir(cat.dir))
	}
	p, err := plugin.NewBasePlugin(options...)
	if err != nil {
		return nil, err
	}
	return &serviceInfo{
		name:       name,
		category:   category,
		pluginName: field.Plugin,
		url:        u.url,
		config:     cfg,
		toml:       content,
		plugin:     p,
	}, nil
}

// startServices starts the target services in category order: simulator,
// engines, vehicles, commanders, monitors, then extras. A service that fails to
// start is reported in the returned error, and the rest are still started.
func (d *Daemon) startServices(services map[daemonpb.ServiceCategory][]string) error {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	var errs []error
	for _, category := range startOrder {
		for _, name := range services[category] {
			s := d.findService(category, name)
			if s == nil {
				errs = append(errs, status.Errorf(codes.NotFound, "no %s service %q", categories[category].pluginType, name))
				continue
			}
			if s.broken() {
				errs = append(errs, status.Errorf(codes.FailedPrecondition, "%s %q couldn't be set up: %v",
					categories[category].pluginType, name, s.err))
				continue
			}
			if s.running() {
				continue
			}
			// Release what is left of a run that exited on its own
			s.release()
			var err error
			switch category {
			case daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:
				err = d.startEngine(s)
			case daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:
				err = d.startVehicle(s)
			default:
				err = d.startGenericService(s)
			}
			s.err = err
			if err != nil {
				d.log.Error().Err(err).Str("service", name).Msg("could not start service")
				errs = append(errs, fmt.Errorf("%s %q: %w", categories[category].pluginType, name, err))
				continue
			}
			s.started = time.Now()
			d.log.Info().Str("service", name).Str("category", category.String()).Msg("service started")
		}
	}
	return errors.Join(errs...)
}

// stopServices stops the target services in reverse category order, and waits
// for them to exit. The services are kept, so they can be started again.
func (d *Daemon) stopServices(services map[daemonpb.ServiceCategory][]string) error {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	var errs []error
	for i := len(startOrder) - 1; i >= 0; i-- {
		category := startOrder[i]
		for _, name := range services[category] {
			s := d.findService(category, name)
			if s == nil {
				errs = append(errs, status.Errorf(codes.NotFound, "no %s service %q", categories[category].pluginType, name))
				continue
			}
			if s.cancel == nil {
				continue
			}
			s.release()
			d.log.Info().Str("service", name).Str("category", category.String()).Msg("service stopped")
		}
	}
	return errors.Join(errs...)
}

// startGenericService starts a plugin that hosts a service. The daemon serves
// the plugin's listener, so the plugin can call the daemon with its category's
// AuthCode. The caller must hold svcMu.
func (d *Daemon) startGenericService(s *serviceInfo) error {
	ctx, cancel := context.WithCancel(d.ctx)
	ln, conn, err := s.plugin.Start(ctx)
	if err != nil {
		cancel()
		return err
	}
	s.ln, s.conn, s.cancel = ln, conn, cancel
	if ln != nil {
		go func() {
			if err := d.relay.Serve(ln); err != nil {
				d.log.Debug().Err(err).Str("service", s.name).Msg("plugin listener closed")
			}
		}()
	}
	return nil
}

// startEngine starts an engine plugin, which serves at an iceoryx endpoint
// named after the engine. Like other plugins, the daemon serves its listener.
// The caller must hold svcMu.
func (d *Daemon) startEngine(s *serviceInfo) error {
	if err := d.startGenericService(s); err != nil {
		return err
	}
	s.endpoint = s.name
	return nil
}

// startVehicle starts a vehicle on its driver plugin. The vehicle is created
// on its first start. Each run gets a new in-process daemon listener, and the
// router sends calls with the vehicle's name as their route key to a client
// connection on it.
func (d *Daemon) startVehicle(s *serviceInfo) error {
	if s.vehicle == nil {
		options := []vehicle.VehicleOption{vehicle.WithName(s.name), vehicle.WithLogger(d.log)}
		if d.rcsAddr != "" {
			options = append(options, vehicle.WithRemoteCompute(d.rcsAddr, d.rcsCert))
		}
		v, err := vehicle.NewVehicle(s.plugin, s.config, options...)
		if err != nil {
			return err
		}
		s.vehicle = v
	}
	ln := listener.NewLocalListener(listener.AdminCode)
	conn, err := grpc.NewClient(
		"passthrough:///"+s.name,
		grpc.WithContextDialer(ln.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		ln.Close()
		return err
	}
	ctx, cancel := context.WithCancel(d.ctx)
	if err := s.vehicle.Start(ctx, ln); err != nil {
		cancel()
		conn.Close()
		ln.Close()
		return err
	}
	d.router.AddHeaderRoute(s.name, conn)
	if d.selfAddr.IsValid() {
		d.router.AddHeaderRoute(d.selfAddr.String()+"/"+s.name, conn)
	}
	s.conn, s.cancel = conn, cancel
	return nil
}

// listServices describes all gathered services in start order.
func (d *Daemon) listServices() []*daemonpb.ActiveService {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	var active []*daemonpb.ActiveService
	for _, category := range startOrder {
		for _, s := range d.services[category] {
			running := s.running()
			var uptime *durationpb.Duration
			if running {
				uptime = durationpb.New(time.Since(s.started))
			}
			active = append(active, daemonpb.ActiveService_builder{
				Srv:     daemonpb.Service_builder{Name: s.name, Category: category}.Build(),
				Plugin:  s.pluginName,
				Url:     s.url,
				Running: running,
				Uptime:  uptime,
				Error:   s.errorString(),
			}.Build())
		}
	}
	return active
}

// findService returns the named service in a category, or nil if there is
// none. The caller must hold svcMu.
func (d *Daemon) findService(category daemonpb.ServiceCategory, name string) *serviceInfo {
	for _, s := range d.services[category] {
		if s.name == name {
			return s
		}
	}
	return nil
}

// allServices returns the names of all gathered services that were set up, by
// category.
func (d *Daemon) allServices() map[daemonpb.ServiceCategory][]string {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	all := make(map[daemonpb.ServiceCategory][]string)
	for category, services := range d.services {
		for _, s := range services {
			if s.broken() {
				continue
			}
			all[category] = append(all[category], s.name)
		}
	}
	return all
}

// controllableServices validates a request for services that can be restarted.
func (d *Daemon) controllableServices(services []*daemonpb.Service) (map[daemonpb.ServiceCategory][]string, error) {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	targets := make(map[daemonpb.ServiceCategory][]string)
	for _, s := range services {
		switch s.GetCategory() {
		case daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE,
			daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR,
			daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:
		default:
			return nil, status.Errorf(codes.InvalidArgument,
				"service %q has category %s, only vehicles, monitors and engines can be restarted; use Configure for the rest",
				s.GetName(), s.GetCategory())
		}
		found := d.findService(s.GetCategory(), s.GetName())
		if found == nil {
			return nil, status.Errorf(codes.NotFound, "no %s service %q",
				categories[s.GetCategory()].pluginType, s.GetName())
		}
		if found.broken() {
			return nil, status.Errorf(codes.FailedPrecondition, "%s %q couldn't be set up: %v",
				categories[s.GetCategory()].pluginType, s.GetName(), found.err)
		}
		targets[s.GetCategory()] = append(targets[s.GetCategory()], s.GetName())
	}
	return targets, nil
}

// running reports whether the service is currently running.
func (s *serviceInfo) running() bool {
	if s.vehicle != nil {
		return s.vehicle.Running.Load()
	}
	if s.broken() {
		return false
	}
	return s.plugin.Running()
}

// broken reports whether the service couldn't be set up, so it can't be
// started.
func (s *serviceInfo) broken() bool {
	return s.plugin == nil
}

// errorString describes why the service couldn't be set up, failed to start,
// or exited on its own, or is empty if it didn't. The caller must hold svcMu.
func (s *serviceInfo) errorString() string {
	if s.err != nil {
		return s.err.Error()
	}
	if s.cancel == nil || s.running() {
		return ""
	}
	// Started, but no longer running, so the run has already ended and the
	// vehicle doesn't block for its error
	if s.vehicle != nil {
		if err := s.vehicle.Wait(); err != nil {
			return "exited: " + err.Error()
		}
	}
	return "exited"
}

// pluginTomls returns the plugin toml of each service that was set up, keyed
// by "{category}/{name}" with the category in lowercase.
func (d *Daemon) pluginTomls() map[string][]byte {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	tomls := make(map[string][]byte)
	for category, services := range d.services {
		prefix := strings.ToLower(strings.TrimPrefix(category.String(), "SERVICE_CATEGORY_"))
		for _, s := range services {
			if s.toml != nil {
				tomls[prefix+"/"+s.name] = s.toml
			}
		}
	}
	return tomls
}

// vehicleNames returns the names of all gathered vehicles.
func (d *Daemon) vehicleNames() []string {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	var names []string
	for _, s := range d.services[daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE] {
		if !s.broken() {
			names = append(names, s.name)
		}
	}
	return names
}

// release stops the current run of the service, if any, waits for it to
// exit, and closes its connections. The caller must hold svcMu.
func (s *serviceInfo) release() {
	if s.cancel == nil {
		return
	}
	s.cancel()
	s.cancel = nil
	if s.vehicle != nil {
		s.vehicle.Wait()
	} else {
		s.plugin.Wait()
	}
	if s.conn != nil {
		s.conn.Close()
		s.conn = nil
	}
	s.ln = nil
}
