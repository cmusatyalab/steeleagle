package main

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/internal/tailscale"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// DefaultControlPort is the port eagled's control-plane API listens on.
const DefaultControlPort = 9090

// StopTimeout bounds how long StopVehicles/RestartVehicles wait for a vehicle
// to actually finish tearing down before reporting failure.
const StopTimeout = 15 * time.Second

// runningVehicle tracks one currently-running (or being-torn-down) vehicle.
type runningVehicle struct {
	cancel context.CancelFunc
	done   <-chan struct{}
	port   int // port its listener is bound on
}

// daemon implements eagledpb.DaemonServiceServer. It holds no configuration
// until the first Configure call. That call's daemon-wide settings (such as
// gabriel and swarm-controller) are established once and reused by every later
// call, which only start whatever new vehicles that call lists.
type daemon struct {
	eagledpb.UnimplementedDaemonServiceServer

	ctx      context.Context    // canceled on daemon shutdown, stops every vehicle and its registration stream
	shutdown context.CancelFunc // cancels ctx, ResetConfig calls this itself to trigger the same shutdown a signal would

	mu             sync.Mutex
	configured     bool
	baseCfg        Config // last-applied config, minus Vehicles
	daemonName     string // resolved from baseCfg
	pluginDir      string // plugin runtime directory
	vehicleAuthKey string // tsnet auth key every vehicle joins with
	vehicleVPN     bool   // resolved from baseCfg.VehicleVPN
	gabrielCfg     GabrielConfig
	swarmCfg       SwarmControllerConfig
	nextPort       int                                // next port to assign to a vehicle
	running        map[string]*runningVehicle         // name -> running vehicle; nil value means "reserved, spawn in progress"
	vehicleCfgs    map[string]VehicleConfig           // vehicle configurations
	installed      map[string]installedPluginRecord   // plugin name -> {ref, category}
	aviaryCommand  []string                           // resolved from baseCfg.Aviary.Command
	aviaryDir      string                             // resolved from baseCfg.Aviary.Dir

	// configMu and aviaryMu each serialize their own slow, one-time setup
	// call (tailscale.NewServer, spawnAviary) across concurrent RPCs, without
	// forcing every other RPC to wait on mu for that same duration. Guard
	// only the field(s) named after them; every other field stays under mu.
	configMu      sync.Mutex
	aviaryMu      sync.Mutex
	aviaryStarted bool // whether the shared aviary simulator has been spawned; guarded by aviaryMu
}

// newDaemon constructs a new eagled daemon.
func newDaemon(ctx context.Context, shutdown context.CancelFunc) *daemon {
	return &daemon{
		ctx:         ctx,
		shutdown:    shutdown,
		running:     make(map[string]*runningVehicle),
		vehicleCfgs: make(map[string]VehicleConfig),
		installed:   make(map[string]installedPluginRecord),
	}
}

// Configure parses req's TOML document and starts the vehicles it describes.
func (d *daemon) Configure(ctx context.Context, req *eagledpb.ConfigureRequest) (*eagledpb.ConfigureResponse, error) {
	cfg, err := decodeConfig(req.GetConfigToml())
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "parsing config: %v", err)
	}
	log.Info().Int("vehicles", len(cfg.Vehicles)).Msg("Configure received")
	if err := d.ensureConfigured(cfg); err != nil {
		return nil, err
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
	return eagledpb.ConfigureResponse_builder{Vehicles: results}.Build(), nil
}

// StopVehicles stops each named vehicle without forgetting it: it stays known
// to the daemon, so RestartVehicles can bring it back. It comes back on a
// subsequent eagled restart same as any other configured vehicle.
func (d *daemon) StopVehicles(ctx context.Context, req *eagledpb.StopVehiclesRequest) (*eagledpb.StopVehiclesResponse, error) {
	log.Info().Strs("vehicles", req.GetNames()).Msg("StopVehicles received")
	results := make([]*eagledpb.VehicleResult, 0, len(req.GetNames()))
	for _, name := range req.GetNames() {
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
	results := make([]*eagledpb.VehicleResult, 0, len(req.GetNames()))
	for _, name := range req.GetNames() {
		if err := d.restartOne(name); err != nil {
			log.Warn().Str("vehicle", name).Err(err).Msg("failed to restart vehicle")
			results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: err.Error()}.Build())
			continue
		}
		results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: true}.Build())
	}
	return eagledpb.RestartVehiclesResponse_builder{Vehicles: results}.Build(), nil
}

// ForgetVehicles stops each named vehicle (if running) and forgets it: it will
// not come back on RestartVehicles or a subsequent eagled restart unless
// reconfigured.
func (d *daemon) ForgetVehicles(ctx context.Context, req *eagledpb.ForgetVehiclesRequest) (*eagledpb.ForgetVehiclesResponse, error) {
	log.Info().Strs("vehicles", req.GetNames()).Msg("ForgetVehicles received")
	results := make([]*eagledpb.VehicleResult, 0, len(req.GetNames()))
	for _, name := range req.GetNames() {
		d.mu.Lock()
		_, known := d.vehicleCfgs[name]
		rv, running := d.running[name]
		d.mu.Unlock()
		if !known {
			results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: fmt.Sprintf("vehicle %q not configured", name)}.Build())
			continue
		}
		if running && rv == nil {
			// rv == nil means reserve() has claimed the name but startVehicles
			// hasn't finished spawning it yet. Forgetting now would race: if
			// we deleted vehicleCfgs here, startVehicles would just
			// unconditionally re-add it once the spawn completes, silently
			// undoing this call.
			results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: fmt.Sprintf("vehicle %q is still starting, try again", name)}.Build())
			continue
		}

		if running && rv != nil {
			if err := d.stopOne(name); err != nil {
				results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: false, Error: err.Error()}.Build())
				continue
			}
		}
		d.mu.Lock()
		delete(d.vehicleCfgs, name)
		d.mu.Unlock()
		results = append(results, eagledpb.VehicleResult_builder{Name: name, Ok: true}.Build())
	}
	d.persist()
	return eagledpb.ForgetVehiclesResponse_builder{Vehicles: results}.Build(), nil
}

// startVehicles spawns each of vehicleCfgs, reporting a per-vehicle result
// rather than aborting the whole batch on one failure.
func (d *daemon) startVehicles(vehicleCfgs []VehicleConfig) []*eagledpb.VehicleResult {
	d.mu.Lock()
	pluginDir, authKey, vehicleVPN := d.pluginDir, d.vehicleAuthKey, d.vehicleVPN
	gabrielCfg, swarmCfg, daemonName := d.gabrielCfg, d.swarmCfg, d.daemonName
	d.mu.Unlock()

	results := make([]*eagledpb.VehicleResult, 0, len(vehicleCfgs))
	for _, vehicleCfg := range vehicleCfgs {
		port, err := d.reserve(vehicleCfg.Name)
		if err != nil {
			results = append(results, eagledpb.VehicleResult_builder{
				Name: vehicleCfg.Name, Ok: false, Error: err.Error(),
			}.Build())
			continue
		}

		driverPlugin, missionPlugin, extraPlugins, err := resolvePlugins(vehicleCfg, pluginDir)
		if err != nil {
			d.mu.Lock()
			delete(d.running, vehicleCfg.Name)
			d.mu.Unlock()
			results = append(results, eagledpb.VehicleResult_builder{
				Name: vehicleCfg.Name, Ok: false, Error: err.Error(),
			}.Build())
			continue
		}

		cancel, done, err := spawnVehicle(d.ctx, vehicleCfg, port, driverPlugin, missionPlugin, extraPlugins, authKey, vehicleVPN, gabrielCfg, swarmCfg, daemonName)
		if err != nil {
			d.mu.Lock()
			delete(d.running, vehicleCfg.Name)
			d.mu.Unlock()
			results = append(results, eagledpb.VehicleResult_builder{
				Name: vehicleCfg.Name, Ok: false, Error: err.Error(),
			}.Build())
			continue
		}

		d.mu.Lock()
		d.running[vehicleCfg.Name] = &runningVehicle{cancel: cancel, done: done, port: port}
		d.vehicleCfgs[vehicleCfg.Name] = vehicleCfg
		d.mu.Unlock()
		d.watchExit(vehicleCfg.Name, done)

		results = append(results, eagledpb.VehicleResult_builder{Name: vehicleCfg.Name, Ok: true}.Build())
	}
	return results
}

// watchExit clears name from d.running once done closes, unless a newer
// runningVehicle (e.g. from a concurrent restart) has already replaced it.
func (d *daemon) watchExit(name string, done <-chan struct{}) {
	go func() {
		<-done
		d.mu.Lock()
		if rv, ok := d.running[name]; ok && rv != nil && rv.done == done {
			delete(d.running, name)
		}
		d.mu.Unlock()
	}()
}

// stopOne cancels name's vehicle and waits for it to finish tearing down.
func (d *daemon) stopOne(name string) error {
	d.mu.Lock()
	rv, exists := d.running[name]
	d.mu.Unlock()
	if !exists || rv == nil {
		return fmt.Errorf("vehicle %q not running", name)
	}

	rv.cancel()
	select {
	case <-rv.done:
	case <-time.After(StopTimeout):
		return fmt.Errorf("vehicle %q did not stop within %s", name, StopTimeout)
	}

	d.mu.Lock()
	if cur, ok := d.running[name]; ok && cur == rv {
		delete(d.running, name)
	}
	d.mu.Unlock()
	log.Info().Str("vehicle", name).Msg("vehicle stopped")
	return nil
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
// by that name is already running or being started.
func (d *daemon) reserve(name string) (int, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if _, exists := d.running[name]; exists {
		return 0, fmt.Errorf("vehicle %q already running", name)
	}
	port := d.nextPort
	d.nextPort++
	d.running[name] = nil // placeholder, reserves the name until spawn completes
	return port, nil
}

// ensureConfigured establishes daemon-wide settings from cfg on the first call
// only. Later calls are no-ops. configMu serializes concurrent calls so only
// one ever does the actual setup (including the slow tailscale.NewServer
// call below); mu itself is only held briefly, for the configured check and
// the final field writes, so other RPCs needing mu aren't blocked for the
// whole duration.
func (d *daemon) ensureConfigured(cfg Config) error {
	d.configMu.Lock()
	defer d.configMu.Unlock()

	d.mu.Lock()
	configured := d.configured
	d.mu.Unlock()
	if configured {
		return nil
	}

	if cfg.Backend.SwarmController.Address == "" {
		return status.Error(codes.InvalidArgument, "backend.swarm-controller.address must be set")
	}
	daemonName := cfg.Backend.SwarmController.DaemonName
	if daemonName == "" {
		var err error
		if daemonName, err = os.Hostname(); err != nil {
			return status.Errorf(codes.Internal, "determining daemon name: %v", err)
		}
	}

	pluginDir := cfg.PluginDir
	if pluginDir == "" {
		var err error
		if pluginDir, err = util.GetPluginDir(); err != nil {
			return status.Errorf(codes.Internal, "determining plugin directory: %v", err)
		}
	}

	daemonAuthKey := ""
	if cfg.Tailscale.AuthKeyEnv != "" {
		daemonAuthKey = os.Getenv(cfg.Tailscale.AuthKeyEnv)
	}
	vehicleAuthKeyEnv := cfg.Tailscale.VehicleAuthKeyEnv
	if vehicleAuthKeyEnv == "" {
		vehicleAuthKeyEnv = cfg.Tailscale.AuthKeyEnv
	}
	vehicleAuthKey := ""
	if vehicleAuthKeyEnv != "" {
		vehicleAuthKey = os.Getenv(vehicleAuthKeyEnv)
	}

	// eagled's own tsnet node, separate from any vehicle's. Vehicles each get
	// their own node, joined with vehicleAuthKey, when spawned below.
	if cfg.VPN {
		ts, err := tailscale.NewServer(cfg.Tailscale.Hostname, daemonAuthKey, true)
		if err != nil {
			return status.Errorf(codes.Internal, "starting tailscale: %v", err)
		}
		go func() {
			<-d.ctx.Done()
			ts.Close()
		}()
	}

	// Vehicles are tracked separately in vehicleCfgs
	cfg.Vehicles = nil

	d.mu.Lock()
	d.baseCfg = cfg
	d.daemonName = daemonName
	d.pluginDir = pluginDir
	d.vehicleAuthKey = vehicleAuthKey
	d.vehicleVPN = cfg.VehicleVPN
	d.gabrielCfg = cfg.Gabriel
	d.swarmCfg = cfg.Backend.SwarmController
	d.aviaryCommand = cfg.Aviary.Command
	d.aviaryDir = cfg.Aviary.Dir
	d.nextPort = cfg.PortBase
	d.configured = true
	d.mu.Unlock()
	log.Info().
		Str("daemon-name", daemonName).
		Bool("vpn", cfg.VPN).
		Bool("vehicle-vpn", cfg.VehicleVPN).
		Str("swarm-controller", cfg.Backend.SwarmController.Address).
		Msg("daemon-wide config established")
	return nil
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
