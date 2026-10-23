package daemon

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
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
)

// categoryInfo describes how the services of a category are run.
type categoryInfo struct {
	name        string // lowercase category name, as in plugin toml keys
	pluginType  string // required plugin type in the .plugin.toml
	dir         string // runtime directory for the category's plugins
	restartable bool   // whether RestartServices may restart the category's services
}

// authCode returns the AuthCode that calls from a plugin with the given auth
// level carry to the daemon.
func authCode(auth config.Auth) (listener.AuthCode, error) {
	switch auth.Level() {
	case config.AuthAdmin:
		return listener.AdminCode, nil
	case config.AuthPrivileged:
		return listener.PrivilegedCode, nil
	case config.AuthUser:
		return listener.UserCode, nil
	case config.AuthExternal:
		return listener.ExternalCode, nil
	case config.AuthUnknown:
		return listener.UnknownCode, nil
	}
	return 0, fmt.Errorf("invalid auth %q", auth)
}

// gatherServices reads the services used by the config into d.services
// without starting them. Each service is named by its qualified name, so that
// its plugin, and the vehicle or engine it runs, are unique across the
// network.
func (d *Daemon) gatherServices() error {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	d.services = make(map[daemonpb.ServiceCategory][]*serviceInfo)
	var errs []error
	add := func(name string, category daemonpb.ServiceCategory, auth config.Auth, field config.PluginField) {
		name = d.qualify(name)
		s, err := d.newService(name, category, auth, field)
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
		add(c.Simulator.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR, c.Simulator.Auth, c.Simulator.Plugin)
	}
	for _, s := range c.Engines {
		add(s.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE, s.Auth, s.Plugin)
	}
	for _, v := range c.Vehicles {
		add(v.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE, v.Auth, v.Plugin)
	}
	for _, s := range c.Monitors {
		add(s.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR, s.Auth, s.Plugin)
	}
	for _, s := range c.Extras {
		add(s.Name, daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA, s.Auth, s.Plugin)
	}
	return errors.Join(errs...)
}

// newService finds the plugin for a service in its package and creates the
// plugin, ready to start. The caller must hold svcMu.
func (d *Daemon) newService(
	name string,
	category daemonpb.ServiceCategory,
	auth config.Auth,
	field config.PluginField,
) (*serviceInfo, error) {
	cat := categories[category]
	if name == "" {
		return nil, fmt.Errorf("service has no name")
	}
	if d.findService(category, name) != nil {
		return nil, fmt.Errorf("duplicate service name")
	}
	code, err := authCode(auth)
	if err != nil {
		return nil, err
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
		models, err := util.GetModelDir()
		if err != nil {
			return nil, fmt.Errorf("could not get model directory: %w", err)
		}
		options = append(options, plugin.WithoutClient(), plugin.WithAuthCode(code),
			plugin.WithParentDir(cat.dir), plugin.WithEnvironment(IceoryxServiceEnv, name),
			plugin.WithReadOnlyFiles([]string{models}))
	case daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:
		if cfg.Driver == nil {
			return nil, fmt.Errorf("plugin %q has no driver cap", field.Plugin)
		}
		options = append(options, plugin.WithoutListener(),
			plugin.WithParentDir(filepath.Join(cat.dir, name)))
	default:
		options = append(options, plugin.WithoutClient(),
			plugin.WithAuthCode(code), plugin.WithParentDir(cat.dir))
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

// findService returns the service in a category named by its qualified name,
// or by its name in the config, or nil if there is none. The caller must hold
// svcMu.
func (d *Daemon) findService(category daemonpb.ServiceCategory, name string) *serviceInfo {
	for _, s := range d.services[category] {
		if s.name == name || s.name == d.qualify(name) {
			return s
		}
	}
	return nil
}

// lookupService returns the named service in a category if it was set up, or
// a status error saying why not. The caller must hold svcMu.
func (d *Daemon) lookupService(category daemonpb.ServiceCategory, name string) (*serviceInfo, error) {
	s := d.findService(category, name)
	if s == nil {
		return nil, status.Errorf(codes.NotFound, "no %s service %q", categories[category].pluginType, name)
	}
	if err := s.setupError(); err != nil {
		return nil, err
	}
	return s, nil
}

// eachService calls fn on each gathered service in start order, holding
// svcMu.
func (d *Daemon) eachService(fn func(*serviceInfo)) {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	for _, category := range startOrder {
		for _, s := range d.services[category] {
			fn(s)
		}
	}
}

// selectServices returns the gathered services that keep accepts, or all of
// them if keep is nil, in start order. keep is called holding svcMu.
func (d *Daemon) selectServices(keep func(*serviceInfo) bool) []*serviceInfo {
	var selected []*serviceInfo
	d.eachService(func(s *serviceInfo) {
		if keep == nil || keep(s) {
			selected = append(selected, s)
		}
	})
	return selected
}

// startServices starts services in category order: simulator, engines,
// vehicles, monitors, then extras. A service that fails to start
// is reported in the returned error, and the rest are still started.
func (d *Daemon) startServices(services []*serviceInfo) error {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	var errs []error
	for _, category := range startOrder {
		for _, s := range services {
			if s.category != category || s.running() {
				continue
			}
			if err := s.setupError(); err != nil {
				errs = append(errs, err)
				continue
			}
			// Release what is left of a run that exited on its own
			s.release()
			s.err = d.startService(s)
			if s.err != nil {
				d.log.Error().Err(s.err).Str("service", s.name).Msg("could not start service")
				errs = append(errs, fmt.Errorf("%s %q: %w", categories[category].pluginType, s.name, s.err))
				continue
			}
			s.started = time.Now()
			d.log.Info().Str("service", s.name).Str("category", category.String()).Msg("service started")
		}
	}
	return errors.Join(errs...)
}

// stopServices stops services in reverse category order, and waits for them
// to exit. The services are kept, so they can be started again.
func (d *Daemon) stopServices(services []*serviceInfo) {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	for i := len(startOrder) - 1; i >= 0; i-- {
		for _, s := range services {
			if s.category != startOrder[i] || s.cancel == nil {
				continue
			}
			s.release()
			d.log.Info().Str("service", s.name).Str("category", s.category.String()).Msg("service stopped")
		}
	}
}

// startService starts a run of a service. A vehicle runs on its driver plugin,
// and is created on its first start; each run gets a new in-process daemon
// listener, and the router sends calls with the vehicle's name as their route
// key to a client connection on it.
func (d *Daemon) startService(s *serviceInfo) error {
	ctx, cancel := context.WithCancel(d.ctx)
	if s.category != daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE {
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

	if s.vehicle == nil {
		options := []vehicle.VehicleOption{vehicle.WithName(s.name), vehicle.WithLogger(d.log),
			vehicle.WithLcs(d.Config.Daemon.Hostname), vehicle.WithAvailableEngines(d.availableEngines())}
		d.rcsMu.Lock()
		if d.rcsAddr != "" {
			options = append(options, vehicle.WithRcs(d.rcsAddr, d.rcsCert))
		}
		d.rcsMu.Unlock()
		v, err := vehicle.NewVehicle(s.plugin, s.config, options...)
		if err != nil {
			cancel()
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
		cancel()
		ln.Close()
		return err
	}
	if err := s.vehicle.Start(ctx, ln); err != nil {
		cancel()
		conn.Close()
		ln.Close()
		return err
	}
	d.router.AddHeaderRoute(s.name, conn)
	s.conn, s.cancel = conn, cancel
	return nil
}

// closeServices releases what services hold beyond their runs, like the Uriel
// client of each vehicle and the dataflow installed on it. The services must
// be stopped, and their vehicles are created again if they are started.
func (d *Daemon) closeServices() {
	d.eachService(func(s *serviceInfo) {
		if s.vehicle == nil {
			return
		}
		if err := s.vehicle.Close(); err != nil {
			d.log.Warn().Err(err).Str("service", s.name).Msg("could not close vehicle")
		}
		s.vehicle = nil
	})
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

// setUp reports whether the service was set up, so it can be started.
func (s *serviceInfo) setUp() bool {
	return s.plugin != nil
}

// setupError returns why the service couldn't be set up, as a status error,
// or nil if it was.
func (s *serviceInfo) setupError() error {
	if s.setUp() {
		return nil
	}
	return status.Errorf(codes.FailedPrecondition, "%s %q couldn't be set up: %v",
		categories[s.category].pluginType, s.name, s.err)
}

// running reports whether the service is currently running.
func (s *serviceInfo) running() bool {
	if s.vehicle != nil {
		return s.vehicle.Running.Load()
	}
	if !s.setUp() {
		return false
	}
	return s.plugin.Running()
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
