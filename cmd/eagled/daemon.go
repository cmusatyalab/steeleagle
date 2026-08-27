package main

import (
	"context"
	"fmt"
	"os"
	"reflect"
	"runtime/debug"
	"sync"
	"time"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/internal/tailscale"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// gabrielModulePath and steeleagleProtocolModulePath are the module paths
// whose resolved versions are logged on every Configure call.
const (
	gabrielModulePath            = "github.com/cmusatyalab/gabriel/go-client"
	steeleagleProtocolModulePath = "github.com/cmusatyalab/steeleagle/api/go"
)

// moduleVersion returns the resolved version of the named dependency recorded
// in this binary's build info (replace directives take priority over the
// required version), or "unknown" if it can't be determined.
func moduleVersion(path string) string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return "unknown"
	}
	for _, dep := range info.Deps {
		if dep.Path != path {
			continue
		}
		if dep.Replace != nil {
			return dep.Replace.Version
		}
		return dep.Version
	}
	return "unknown"
}

// DefaultControlPort is the port eagled's control-plane API listens on.
const DefaultControlPort = 9090

// StopTimeout bounds how long StopVehicles/RestartVehicles wait for a vehicle
// to actually finish tearing down before reporting failure.
const StopTimeout = 30 * time.Second

// TailscaleStartTimeout bounds how long we wait for a tsnet node to join the
// tailnet.
const TailscaleStartTimeout = 30 * time.Second

// installedPluginKey identifies one installed plugin. The same name can be
// installed independently under different categories (each category is its
// own directory, see util.GetInstalledPluginDir), so category is part of the
// key rather than side metadata.
type installedPluginKey struct {
	Name     string
	Category string
}

// runningVehicle tracks one vehicle from the moment its name is reserved
// through spawning, running, and teardown. cancel is set as soon as the name
// is reserved (before spawnVehicle is even called), so a stop/restart/reset
// request can always interrupt it.
type runningVehicle struct {
	cancel      context.CancelFunc
	ready       chan struct{}   // closed once the spawn attempt finishes, successfully or not
	err         error           // set if the spawn attempt failed; only meaningful once ready is closed
	done        <-chan struct{} // closed once a successfully-spawned vehicle exits; nil if the spawn failed
	port        int             // port its listener is bound on
	promPort    int             // port its Gabriel client serves Prometheus metrics on; 0 if disabled
	configStale bool            // true once a Configure call has replaced d.vehicleCfgs[name] out from under this still-running process; guarded by d.mu, like d.running itself
}

// running reports whether rv's spawn attempt finished successfully and the
// vehicle hasn't exited yet. Safe to call whether or not the spawn attempt has
// finished.
func (rv *runningVehicle) running() bool {
	select {
	case <-rv.ready:
		return rv.err == nil
	default:
		return false // still spawning
	}
}

// daemon implements eagledpb.DaemonServiceServer.
type daemon struct {
	eagledpb.UnimplementedDaemonServiceServer

	ctx      context.Context    // canceled on daemon shutdown, stops every vehicle and its registration stream
	shutdown context.CancelFunc // cancels ctx, ResetConfig calls this itself to trigger the same shutdown a signal would

	grpcServer  *grpc.Server // gRPC server to serve DaemonService on
	controlPort int          // port gRPC server listens on

	mu                 sync.Mutex
	configured         bool
	tsServer           *tailscale.Server // eagled's own tsnet node, once started; nil until then
	tsHostname         string            // hostname tsServer is currently running under
	baseCfg            Config            // last-applied config, minus Vehicles
	daemonName         string            // resolved from baseCfg
	pluginDir          string            // plugin runtime directory
	vehicleAuthKey     string            // tsnet auth key every vehicle joins with
	vehicleMemStore    bool              // whether vehicles keep tsnet state in memory instead of persisting it to disk
	gabrielCfg         GabrielConfig
	swarmCfg           SwarmControllerConfig
	nextPort           int                           // next port to assign to a vehicle
	nextPrometheusPort int                           // next port to assign a vehicle's Gabriel client metrics endpoint; 0 if disabled
	running            map[string]*runningVehicle    // name -> vehicle, from the moment its name is reserved through teardown
	vehicleCfgs        map[string]VehicleConfig      // vehicle configurations
	installed          map[installedPluginKey]string // {name, category} -> ref
	aviaryCommand      []string                      // resolved from baseCfg.Aviary.Command
	aviaryDir          string                        // resolved from baseCfg.Aviary.Dir

	// configMu and aviaryMu each serialize their own slow, one-time setup
	// call (tailscale.NewServer, spawnAviary) across concurrent RPCs, without
	// forcing every other RPC to wait on mu for that same duration.
	configMu      sync.Mutex
	aviaryMu      sync.Mutex
	aviaryStarted bool // whether the shared aviary simulator has been spawned; guarded by aviaryMu

	// installLocks serializes InstallPlugin calls per {name, category}
	installLocks map[installedPluginKey]*sync.Mutex
}

// lockInstall returns the mutex serializing InstallPlugin calls for key,
// creating one on first use.
func (d *daemon) lockInstall(key installedPluginKey) *sync.Mutex {
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.installLocks == nil {
		d.installLocks = make(map[installedPluginKey]*sync.Mutex)
	}
	mu, ok := d.installLocks[key]
	if !ok {
		mu = &sync.Mutex{}
		d.installLocks[key] = mu
	}
	return mu
}

// newDaemon constructs a new eagled daemon.
func newDaemon(ctx context.Context, shutdown context.CancelFunc) *daemon {
	return &daemon{
		ctx:         ctx,
		shutdown:    shutdown,
		running:     make(map[string]*runningVehicle),
		vehicleCfgs: make(map[string]VehicleConfig),
		installed:   make(map[installedPluginKey]string),
	}
}

// logConfig logs the daemon-wide config and each vehicle's config, along with
// the resolved gabriel and steeleagle protocol module versions in use. msg
// distinguishes the caller (a Configure RPC vs. reloading persisted config on
// daemon restart) in the log line.
func logConfig(cfg Config, msg string) {
	log.Info().
		Int("port-base", cfg.PortBase).
		Str("plugin-dir", cfg.PluginDir).
		Str("hostname", cfg.Hostname).
		Bool("vehicle-tsnet-mem-store", cfg.VehicleTsnetMemStore).
		Str("gabriel-module-version", moduleVersion(gabrielModulePath)).
		Str("steeleagle-protocol-version", moduleVersion(steeleagleProtocolModulePath)).
		Interface("gabriel", cfg.Gabriel).
		Interface("backend", cfg.Backend).
		Interface("aviary", cfg.Aviary).
		Int("vehicles", len(cfg.Vehicles)).
		Msg(msg)
	for _, vc := range cfg.Vehicles {
		log.Info().Str("vehicle", vc.Name).Interface("config", vc).Msg("vehicle configured")
	}
}

// Configure parses req's TOML document and starts the vehicles it describes.
func (d *daemon) Configure(ctx context.Context, req *eagledpb.ConfigureRequest) (*eagledpb.ConfigureResponse, error) {
	cfg, err := decodeConfig(req.GetConfigToml())
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "parsing config: %v", err)
	}
	logConfig(cfg, "Configure received")
	applied, diverged, err := d.ensureConfigured(cfg)
	if err != nil {
		return nil, err
	}
	if diverged {
		log.Warn().Msg("daemon already configured; some requested daemon-wide settings differ from what's active and were not applied")
	}
	if err := d.ensureAviary(cfg.Vehicles); err != nil {
		return nil, err
	}

	results := d.startVehicles(cfg.Vehicles)
	d.persist()
	for _, r := range results {
		if !r.GetOk() {
			log.Warn().Str("vehicle", r.GetName()).Str("error", r.GetError()).Msg("vehicle failed to start")
		}
	}
	return eagledpb.ConfigureResponse_builder{
		Vehicles:               results,
		DaemonSettingsApplied:  applied,
		DaemonSettingsDiverged: diverged,
	}.Build(), nil
}

// dedupeNames returns names with each value kept only once, in
// first-occurrence order.
func dedupeNames(names []string) []string {
	seen := make(map[string]bool, len(names))
	out := make([]string, 0, len(names))
	for _, name := range names {
		if seen[name] {
			continue
		}
		seen[name] = true
		out = append(out, name)
	}
	return out
}

// StopVehicles stops each named vehicle without forgetting it. These vehicles
// stay known to the daemon, so RestartVehicles can bring it back. They come
// back on a subsequent eagled restart same as any other configured vehicle.
func (d *daemon) StopVehicles(ctx context.Context, req *eagledpb.StopVehiclesRequest) (*eagledpb.StopVehiclesResponse, error) {
	log.Info().Strs("vehicles", req.GetNames()).Msg("StopVehicles received")
	names := dedupeNames(req.GetNames())
	results := make([]*eagledpb.VehicleResult, 0, len(names))
	for _, name := range names {
		if err := d.stopOne(name); err != nil {
			log.Warn().Str("vehicle", name).Err(err).Msg("failed to stop vehicle")
			results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: err.Error()}.Build())
			continue
		}
		results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: true}.Build())
	}
	return eagledpb.StopVehiclesResponse_builder{Vehicles: results}.Build(), nil
}

// RestartVehicles stops and restarts each named vehicle using the
// configuration it was last started or configured with.
func (d *daemon) RestartVehicles(ctx context.Context, req *eagledpb.RestartVehiclesRequest) (*eagledpb.RestartVehiclesResponse, error) {
	log.Info().Strs("vehicles", req.GetNames()).Msg("RestartVehicles received")
	names := dedupeNames(req.GetNames())
	results := make([]*eagledpb.VehicleResult, 0, len(names))
	for _, name := range names {
		if err := d.restartOne(name); err != nil {
			log.Warn().Str("vehicle", name).Err(err).Msg("failed to restart vehicle")
			results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: err.Error()}.Build())
			continue
		}
		results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: true}.Build())
	}
	return eagledpb.RestartVehiclesResponse_builder{Vehicles: results}.Build(), nil
}

// ForgetVehicles stops each named vehicle (if running) and forgets it. These
// vehicles will not come back on RestartVehicles or a subsequent eagled
// restart unless reconfigured.
func (d *daemon) ForgetVehicles(ctx context.Context, req *eagledpb.ForgetVehiclesRequest) (*eagledpb.ForgetVehiclesResponse, error) {
	log.Info().Strs("vehicles", req.GetNames()).Msg("ForgetVehicles received")
	names := dedupeNames(req.GetNames())
	results := make([]*eagledpb.VehicleResult, 0, len(names))
	for _, name := range names {
		d.mu.Lock()
		_, known := d.vehicleCfgs[name]
		_, running := d.running[name]
		d.mu.Unlock()
		if !known {
			results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: fmt.Sprintf("vehicle %q not configured", name)}.Build())
			continue
		}

		if running {
			// stopOne cancels and waits out the reservation whether it's still
			// spawning or fully running, so by the time it returns name is
			// fully clear of d.running — no race with startVehicles re-adding
			// it underneath us.
			if err := d.stopOne(name); err != nil {
				results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: err.Error()}.Build())
				continue
			}
		}
		d.mu.Lock()
		delete(d.vehicleCfgs, name)
		d.mu.Unlock()
		removeTsnetState(name)
		results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: true}.Build())
	}
	d.persist()
	return eagledpb.ForgetVehiclesResponse_builder{Vehicles: results}.Build(), nil
}

// removeTsnetState deletes a forgotten vehicle's persisted tsnet state, if
// any, so a future vehicle reusing name doesn't inherit a stale node key for a
// device that's already been reaped from the tailnet. Best-effort: a vehicle
// that never joined the tailnet (no auth key, or memStore) has nothing to
// remove, so errors here are only logged.
func removeTsnetState(name string) {
	dir, err := tailscale.StateDir(name)
	if err != nil {
		log.Warn().Err(err).Str("vehicle", name).Msg("could not determine tsnet state directory to clean up")
		return
	}
	if err := os.RemoveAll(dir); err != nil {
		log.Warn().Err(err).Str("vehicle", name).Msg("could not clean up tsnet state directory")
	}
}

// startVehicles spawns each of vehicleCfgs, reporting a per-vehicle result
// rather than aborting the whole batch on one failure.
func (d *daemon) startVehicles(vehicleCfgs []VehicleConfig) []*eagledpb.VehicleResult {
	d.mu.Lock()
	pluginDir, authKey, memStore := d.pluginDir, d.vehicleAuthKey, d.vehicleMemStore
	gabrielCfg, swarmCfg, daemonName := d.gabrielCfg, d.swarmCfg, d.daemonName
	d.mu.Unlock()

	results := make([]*eagledpb.VehicleResult, 0, len(vehicleCfgs))
	for _, vehicleCfg := range vehicleCfgs {
		d.mu.Lock()
		_, existed := d.vehicleCfgs[vehicleCfg.Name]
		rv, present := d.running[vehicleCfg.Name]
		// Check rv.running(), not just present: a reservation may still be
		// mid-spawn (duplicate name in this config, or a racing Configure
		// call). Treating it as "running" here would let its spawn overwrite
		// our config update once it finishes. Fall through to reserve()
		// instead, which correctly rejects the duplicate name.
		running := present && rv.running()
		if running {
			// Leave the running process alone; its new config takes effect
			// next time it's (re)started.
			d.vehicleCfgs[vehicleCfg.Name] = vehicleCfg
			rv.configStale = true
		}
		d.mu.Unlock()
		if running {
			results = append(results, eagledpb.VehicleResult_builder{
				Name: vehicleCfg.Name, Ok: true, Reconfigured: true, RestartRequired: true,
			}.Build())
			continue
		}

		rv, vCtx, err := d.reserve(vehicleCfg.Name)
		if err != nil {
			results = append(results, eagledpb.VehicleResult_builder{
				Name: vehicleCfg.Name, Ok: false, Error: err.Error(),
			}.Build())
			continue
		}

		spawn := func() error {
			return d.startOne(vCtx, rv, vehicleCfg, pluginDir, authKey, memStore, gabrielCfg, swarmCfg, daemonName)
		}

		if !vehicleCfg.Simulate {
			if ip := driverIP(vehicleCfg); ip == "" {
				log.Warn().Str("vehicle", vehicleCfg.Name).
					Msg("no drone IP found in driver args (expected \"--ip <address>\"), skipping reachability probe")
			} else if err := probeDroneReachable(vCtx, ip); err != nil {
				// Not reachable yet. Rather than fail Configure outright,
				// remember the vehicle as desired (so it survives an eagled
				// restart, and ForgetVehicles/StopVehicles can still cancel
				// it) and keep retrying in the background until it comes up or
				// is canceled.
				log.Warn().Str("vehicle", vehicleCfg.Name).Str("ip", ip).Err(err).
					Msg("drone not reachable yet, will keep retrying in the background")
				d.mu.Lock()
				d.vehicleCfgs[vehicleCfg.Name] = vehicleCfg
				d.mu.Unlock()
				go func() {
					if err := waitForDrone(vCtx, vehicleCfg.Name, ip); err != nil {
						d.failSpawn(vehicleCfg.Name, rv, err)
						return
					}
					if err := spawn(); err != nil {
						log.Warn().Str("vehicle", vehicleCfg.Name).Err(err).
							Msg("vehicle failed to start after drone became reachable")
					}
				}()
				results = append(results, eagledpb.VehicleResult_builder{Name: vehicleCfg.Name, Ok: true, Reconfigured: existed}.Build())
				continue
			}
		}

		if err := spawn(); err != nil {
			results = append(results, eagledpb.VehicleResult_builder{
				Name: vehicleCfg.Name, Ok: false, Error: err.Error(),
			}.Build())
			continue
		}
		results = append(results, eagledpb.VehicleResult_builder{Name: vehicleCfg.Name, Ok: true, Reconfigured: existed}.Build())
	}
	return results
}

// startOne resolves vehicleCfg's plugins and spawns it on the already reserved
// rv, recording it in d.vehicleCfgs and watching for its exit. On error, rv's
// reservation is released via failSpawn so the name is free to retry.
func (d *daemon) startOne(
	vCtx context.Context,
	rv *runningVehicle,
	vehicleCfg VehicleConfig,
	pluginDir, authKey string,
	memStore bool,
	gabrielCfg GabrielConfig,
	swarmCfg SwarmControllerConfig,
	daemonName string,
) error {
	driverPlugin, missionPlugin, extraPlugins, err := resolvePlugins(vehicleCfg, pluginDir)
	if err != nil {
		d.failSpawn(vehicleCfg.Name, rv, err)
		return err
	}

	done, err := spawnVehicle(vCtx, vehicleCfg, rv.port, rv.promPort, driverPlugin, missionPlugin, extraPlugins, authKey, memStore, gabrielCfg, swarmCfg, daemonName)
	if err != nil {
		d.failSpawn(vehicleCfg.Name, rv, err)
		return err
	}

	d.mu.Lock()
	rv.done = done
	close(rv.ready)
	d.vehicleCfgs[vehicleCfg.Name] = vehicleCfg
	d.mu.Unlock()
	d.watchExit(vehicleCfg.Name, done)
	return nil
}

// failSpawn records name's failed spawn attempt on rv (unblocking anything
// waiting on rv.ready, e.g. a concurrent stopOne), releases rv's context
// (never started, so nothing else will), and, unless a newer reservation has
// already replaced rv, removes name from d.running so the name is free to try
// again.
func (d *daemon) failSpawn(name string, rv *runningVehicle, err error) {
	rv.cancel()
	d.mu.Lock()
	if cur, ok := d.running[name]; ok && cur == rv {
		delete(d.running, name)
	}
	d.mu.Unlock()
	rv.err = err
	close(rv.ready)
}

// watchExit clears name from d.running once done closes, unless a newer
// runningVehicle (e.g. from a concurrent restart) has already replaced it.
func (d *daemon) watchExit(name string, done <-chan struct{}) {
	go func() {
		<-done
		d.mu.Lock()
		if rv, ok := d.running[name]; ok && rv.done == done {
			delete(d.running, name)
		}
		d.mu.Unlock()
	}()
}

// stopOne cancels name's vehicle and waits for it to finish tearing down.
// This works whether the vehicle is fully running or still spawning (e.g.
// stuck joining the tailnet): cancel is set as soon as the name is reserved,
// so it always interrupts whatever's in progress instead of requiring the
// caller to wait out a stuck spawn.
func (d *daemon) stopOne(name string) error {
	d.mu.Lock()
	rv, exists := d.running[name]
	d.mu.Unlock()
	if !exists {
		return fmt.Errorf("vehicle %q not running", name)
	}

	rv.cancel()

	select {
	case <-rv.ready:
	case <-time.After(StopTimeout):
		return fmt.Errorf("vehicle %q did not stop within %s", name, StopTimeout)
	}
	if rv.done != nil {
		// The spawn succeeded before cancellation took effect: wait for the
		// now-canceled vehicle to actually finish tearing down.
		select {
		case <-rv.done:
		case <-time.After(StopTimeout):
			return fmt.Errorf("vehicle %q did not stop within %s", name, StopTimeout)
		}
	}

	d.mu.Lock()
	if cur, ok := d.running[name]; ok && cur == rv {
		delete(d.running, name)
	}
	d.mu.Unlock()
	log.Info().Str("vehicle", name).Msg("vehicle stopped")
	return nil
}

// stopAll stops every vehicle currently reserved, spawning, or running
// (canceling any still mid-spawn rather than waiting on it). Best-effort: used
// by ResetConfig, which is shutting the whole daemon down regardless, so one
// vehicle failing to stop within StopTimeout shouldn't block the rest.
func (d *daemon) stopAll() {
	d.mu.Lock()
	names := make([]string, 0, len(d.running))
	for name := range d.running {
		names = append(names, name)
	}
	d.mu.Unlock()

	for _, name := range names {
		if err := d.stopOne(name); err != nil {
			log.Warn().Str("vehicle", name).Err(err).Msg("failed to stop vehicle")
		}
	}
}

// restartOne stops a vehicle (if running) and starts it again using its
// last-known configuration.
func (d *daemon) restartOne(name string) error {
	d.mu.Lock()
	vehicleCfg, known := d.vehicleCfgs[name]
	_, running := d.running[name]
	d.mu.Unlock()
	if !known {
		return fmt.Errorf("vehicle %q not configured", name)
	}
	if running {
		if err := d.stopOne(name); err != nil {
			return err
		}
	}

	results := d.startVehicles([]VehicleConfig{vehicleCfg})
	if !results[0].GetOk() {
		return fmt.Errorf("%s", results[0].GetError())
	}
	return nil
}

// reserve claims the next available port for a vehicle, failing if a vehicle
// by that name is already running or being started. The returned context is
// canceled the moment rv.cancel is called (directly, or via d.ctx being
// canceled on daemon shutdown). spawnVehicle must use it throughout, so the
// spawn can be interrupted even while it's still in progress.
func (d *daemon) reserve(name string) (rv *runningVehicle, vCtx context.Context, err error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if rv, exists := d.running[name]; exists {
		if rv.running() {
			return nil, nil, fmt.Errorf("vehicle %q already running", name)
		}
		return nil, nil, fmt.Errorf("vehicle %q is still starting from an earlier request", name)
	}
	port := d.nextPort
	d.nextPort++
	promPort := 0
	if d.nextPrometheusPort != 0 {
		promPort = d.nextPrometheusPort
		d.nextPrometheusPort++
	}
	vCtx, cancel := context.WithCancel(d.ctx)
	rv = &runningVehicle{cancel: cancel, ready: make(chan struct{}), port: port, promPort: promPort}
	d.running[name] = rv
	return rv, vCtx, nil
}

// resolveHostname returns hostname if set, otherwise the OS hostname suffixed
// with "-eagled".
func resolveHostname(hostname string) (string, error) {
	if hostname != "" {
		return hostname, nil
	}
	osHostname, err := os.Hostname()
	return osHostname + "-eagled", err
}

// networked reports whether eagled's tsnet node is already up.
func (d *daemon) networked() bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.tsServer != nil
}

// ensureNetwork starts eagled's tsnet node and serves DaemonService over it,
// if it isn't already up. Used at startup only (from the persisted network
// config, and as a fallback from loadPersisted): ensureConfigured calls
// ensureNetworkLocked directly, since it already holds configMu by the time it
// needs to join.
func (d *daemon) ensureNetwork(cfg Config) error {
	d.configMu.Lock()
	defer d.configMu.Unlock()
	return d.ensureNetworkLocked(cfg)
}

// ensureNetworkLocked is ensureNetwork's body, for callers that already hold
// configMu.
func (d *daemon) ensureNetworkLocked(cfg Config) error {
	authKey := os.Getenv(TSAuthKeyEnv)
	if authKey == "" {
		// tailscale not configured
		return nil
	}

	hostname, err := resolveHostname(cfg.Hostname)
	if err != nil {
		return status.Errorf(codes.Internal, "determining hostname: %v", err)
	}

	d.mu.Lock()
	networkConfigured := d.tsServer != nil
	currentHostname := d.tsHostname
	d.mu.Unlock()
	if networkConfigured && currentHostname == hostname {
		return nil
	}

	startCtx, cancel := context.WithTimeout(d.ctx, TailscaleStartTimeout)
	defer cancel()
	ts, err := tailscale.NewServer(startCtx, hostname, authKey, "daemon", false)
	if err != nil {
		return status.Errorf(codes.Internal, "starting tailscale: %v", err)
	}

	// Also serve the control plane through tailscale
	if d.grpcServer != nil {
		tsLn, err := ts.Listen("tcp", d.controlPort)
		if err != nil {
			ts.Close()
			return status.Errorf(codes.Internal, "listening for control plane over tailscale: %v", err)
		}
		go func() {
			if err := d.grpcServer.Serve(tsLn); err != nil {
				log.Warn().Err(err).Msg("DaemonService over tailscale stopped")
			}
		}()
	}

	d.mu.Lock()
	oldTS := d.tsServer
	firstJoin := oldTS == nil
	d.tsServer = ts
	d.tsHostname = hostname
	d.mu.Unlock()

	if oldTS != nil {
		oldTS.Close() // hostname changed: drop the old node, its control-plane listener included
	}
	if firstJoin {
		go func() {
			<-d.ctx.Done()
			d.mu.Lock()
			current := d.tsServer
			d.mu.Unlock()
			current.Close()
		}()
	}

	d.persistNetwork(hostname)
	log.Info().Str("hostname", hostname).Msg("eagled's tsnet node ready")
	return nil
}

// ensureConfigured establishes daemon-wide settings, including eagled's own
// tailscale identity, from cfg on the first Configure call a fresh daemon ever
// receives, and returns applied=true. Later calls are no-ops: applied is
// false, and diverged reports whether cfg's daemon-wide settings (everything
// but Vehicles) differ from what's already active, so an ignored change
// doesn't look identical to one that succeeded.
func (d *daemon) ensureConfigured(cfg Config) (applied, diverged bool, err error) {
	d.configMu.Lock()
	defer d.configMu.Unlock()

	d.mu.Lock()
	configured := d.configured
	active := d.baseCfg
	d.mu.Unlock()
	if configured {
		requested := cfg
		requested.Vehicles = nil
		return false, !reflect.DeepEqual(active, requested), nil
	}

	if cfg.Backend.SwarmController.Address == "" {
		return false, false, status.Error(codes.InvalidArgument, "backend.swarm-controller.address must be set")
	}
	daemonName, err := resolveHostname(cfg.Hostname)
	if err != nil {
		return false, false, status.Errorf(codes.Internal, "determining daemon name: %v", err)
	}

	pluginDir := cfg.PluginDir
	if pluginDir == "" {
		var err error
		if pluginDir, err = util.GetPluginDir(); err != nil {
			return false, false, status.Errorf(codes.Internal, "determining plugin directory: %v", err)
		}
	}

	if !d.networked() {
		if err := d.ensureNetworkLocked(cfg); err != nil {
			return false, false, err
		}
	}

	// Vehicles each get their own tsnet node
	vehicleAuthKey := os.Getenv(TSVehicleAuthKeyEnv)
	if vehicleAuthKey == "" {
		vehicleAuthKey = os.Getenv(TSAuthKeyEnv)
	}

	// Vehicles are tracked separately in vehicleCfgs
	cfg.Vehicles = nil

	d.mu.Lock()
	d.baseCfg = cfg
	d.daemonName = daemonName
	d.pluginDir = pluginDir
	d.vehicleAuthKey = vehicleAuthKey
	d.vehicleMemStore = cfg.VehicleTsnetMemStore
	d.gabrielCfg = cfg.Gabriel
	d.swarmCfg = cfg.Backend.SwarmController
	d.aviaryCommand = cfg.Aviary.Command
	d.aviaryDir = cfg.Aviary.Dir
	d.nextPort = cfg.PortBase
	d.nextPrometheusPort = cfg.Gabriel.PrometheusPortBase
	d.configured = true
	d.mu.Unlock()
	log.Info().
		Str("daemon-name", daemonName).
		Bool("vehicle-vpn", vehicleAuthKey != "").
		Str("swarm-controller", cfg.Backend.SwarmController.Address).
		Msg("daemon-wide config established")
	return true, false, nil
}

// ensureAviary starts the shared aviary simulator the first time a Configure
// call includes any simulated vehicle. Aviary has no way to add a vehicle once
// it's running, so a later call introducing a new simulated vehicle is
// rejected rather than silently ignored.
func (d *daemon) ensureAviary(vehicleCfgs []VehicleConfig) error {
	var simulated []VehicleConfig
	for _, v := range vehicleCfgs {
		if v.Simulate {
			simulated = append(simulated, v)
		}
	}
	if len(simulated) == 0 {
		return nil
	}

	// aviaryMu (not mu) serializes concurrent ensureAviary calls across the
	// whole check-spawn-set sequence, so two concurrent Configure calls can't
	// both see aviaryStarted still false and spawn aviary twice -- without
	// holding mu itself for spawnAviary's duration, which would block every
	// other RPC that only needs mu.
	d.aviaryMu.Lock()
	defer d.aviaryMu.Unlock()
	if d.aviaryStarted {
		return status.Error(codes.FailedPrecondition, "aviary is already running with a fixed set of simulated vehicles; new simulated vehicles require a daemon restart")
	}

	d.mu.Lock()
	command, dir := d.aviaryCommand, d.aviaryDir
	d.mu.Unlock()

	log.Info().Int("vehicles", len(simulated)).Msg("starting shared aviary simulator")
	if err := spawnAviary(d.ctx, command, dir, simulated); err != nil {
		return status.Errorf(codes.Internal, "starting aviary: %v", err)
	}
	d.aviaryStarted = true
	return nil
}
