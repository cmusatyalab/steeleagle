package daemon

import (
	"context"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/netip"
	"os"
	"path/filepath"
	"slices"
	"sync"
	"sync/atomic"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/network"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"github.com/cmusatyalab/steeleagle/v4/core/vehicle"
	uriel "github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// daemonService is a vehicle, engine, or generic service running on the daemon.
type daemonService struct {
	name       string                   // name of the service
	category   daemonpb.ServiceCategory // service category (simulator, vehicle, engine, extra)
	uri        string                   // package uri for this service
	pluginName string                   // plugin file name
	config     *config.PluginConfig     // service plugin config
	auth       listener.AuthCode        // authentication code
	isolation  daemonpb.Isolation       // isolation type
	container  string                   // container url with tag, if isolated in a container
	path       string                   // package directory of the plugin
	args       string                   // plugin args from the daemon config, as a JSON object
	local      bool                     // whether or not the service is local
	simulated  bool                     // whether or not the service belongs to the simulator
}

// daemonPlugin is a plugin running under a daemon service.
type daemonPlugin struct {
	ln        net.Listener       // listener for the plugin
	conn      *grpc.ClientConn   // gRPC connection to the plugin
	plugin    plugin.Plugin      // running plugin reference
	vehicle   *vehicle.Vehicle   // vehicle for this plugin (nil if not a vehicle)
	logStream io.Writer          // log stream
	cancel    context.CancelFunc // cancel function to stop service
}

// orchInfo gives information about this daemon's orchestrator.
type orchInfo struct {
	hostname string           // hostname for the orchestrator
	ip       string           // IP of the orchestrator, where its compute service is
	lcsPort  int              // port of the orchestrator's compute service
	cert     []byte           // DER cert of the orchestrator's compute service
	services []*daemonService // services on the orchestrator
}

// childInfo gives information about a child daemon.
type childInfo struct {
	ip       string           // ip address
	hostname string           // hostname
	conn     *grpc.ClientConn // connection to the child's daemon port
	services []*daemonService // services on the child
}

// Daemon is the SteelEagle daemon. It is responsible for orchestrating
// services based on a config.toml. The config.toml is located in the
// XDG config directory, which defaults to `~/.config`. The daemon can
// optionally be configured by using the command `eagle`.
type Daemon struct {
	daemonpb.UnimplementedDaemonServiceServer
	daemonpb.UnimplementedTransferServiceServer
	Hostname   string                    // daemon hostname
	Config     *config.DaemonConfig      // daemon config
	configPath string                    // path to the daemon config
	Running    atomic.Bool               // whether or not the daemon is currently running
	orch       *orchInfo                 // information about the orchestrator, nil if none
	orchMu     sync.RWMutex              // mutex for orch, which changes on each registration
	regWg      sync.WaitGroup            // registration goroutines
	regCtx     context.Context           // context of the registration, which outlives ctx until the relay stops
	remotes    map[string]*childInfo     // child daemons connected to this daemon as an orchestrator, by IP
	policy     *policy.Policy            // policy for command authorization
	netAuth    string                    // network auth key for this daemon (usually for VPNs)
	netAddr    netip.Addr                // local address of this daemon
	network    network.Network           // network the daemon is on, joined in Run unless given
	socketPath string                    // path of the control socket
	connected  atomic.Bool               // whether or not the daemon is connected to its orchestrator
	router     *router.Router            // network router
	relay      *grpc.Server              // relay gRPC server reference
	server     *grpc.Server              // main gRPC server reference
	lookup     map[string]*daemonService // service lookup table (maps name -> service info)
	services   []*daemonService          // local service list
	plugins    map[string]*daemonPlugin  // plugin info map (maps service name -> plugin info)
	lcs        *uriel.Server             // local compute server reference
	cert       []byte                    // DER cert of the local compute service
	restarting atomic.Bool               // whether or not the daemon is currently restarting
	svcMu      sync.RWMutex              // mutex for lookup, services, plugins, and the plugins themselves
	pkgMu      sync.RWMutex              // mutex for reading or writing packages to .pending
	remMu      sync.RWMutex              // mutex for adding new child daemons
	err        error                     // startup error, if any
	ctx        context.Context           // context for the daemon
	cancel     context.CancelFunc        // cancel function for active contexts
	log        zerolog.Logger            // logger object
}

// Creates a new daemon from the config in the config directory.
func NewDaemon(options ...DaemonOption) (*Daemon, error) {
	daemon := &Daemon{
		Hostname: DefaultHostname,
		log:      zerolog.New(os.Stderr).With().Timestamp().Logger(),
		lookup:   make(map[string]*daemonService),
		plugins:  make(map[string]*daemonPlugin),
		remotes:  make(map[string]*childInfo),
	}
	for _, option := range options {
		option(daemon)
	}

	// Parse the config or write a new one if it doesn't exist
	var err error
	if daemon.configPath == "" {
		configDir, err := util.GetConfigDir()
		if err != nil {
			daemon.log.Error().Err(err).Str("path", configDir).
				Msg("failed to get config directory")
			return nil, err
		}
		daemon.configPath = filepath.Join(configDir, ConfigFileName)
	}
	configPath := daemon.configPath
	if _, err = os.Stat(configPath); errors.Is(err, fs.ErrNotExist) {
		daemon.log.Warn().Str("path", configPath).
			Msg("no daemon config found at path, writing an empty config")
		if err = os.WriteFile(configPath, DefaultConfig, 0644); err != nil {
			daemon.log.Error().Err(err).Str("path", configPath).
				Msg("failed to write to daemon config path")
			return nil, err
		}
	}
	daemon.Config, err = config.ParseDaemonConfigFromFilepath(configPath)
	if err != nil {
		daemon.log.Error().Err(err).Str("path", configPath).
			Msg("failed to parse config, invalid format")
		return nil, err
	}
	daemon.log.Debug().Msg("daemon config loaded")

	// Set hostname from config
	if daemon.Config.Daemon.Hostname != "" {
		daemon.Hostname = daemon.Config.Daemon.Hostname
	}

	// Commit pending installs and removals, which copies packages in the
	// .pending directory into the packages directory
	err = commitPackages()
	if err != nil {
		daemon.log.Error().Err(err).Msg("couldn't commit packages from .pending")
		return nil, err
	}

	// Policy and law setup
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		daemon.log.Error().Err(err).Msg("couldn't parse law")
		return nil, err
	}
	daemon.policy, err = policy.NewPolicy(law, policy.WithLogger(daemon.log))
	if err != nil {
		daemon.log.Error().Err(err).Msg("couldn't create policy")
		return nil, err
	}

	// Set up the router, relay, and server
	daemon.router = router.NewRouter(nil, nil, router.WithLogger(daemon.log))
	daemon.relay = grpc.NewServer(
		grpc.ChainStreamInterceptor(
			daemon.policy.NewStreamPolicyInterceptor(),
			newCallerInterceptor(), // this adds caller IPs to RPC calls
		),
		grpc.ForceServerCodec(router.RawCodec{}),
		grpc.UnknownServiceHandler(daemon.router.Handle),
	)
	daemon.server = grpc.NewServer()
	// Register internal services
	daemonpb.RegisterDaemonServiceServer(daemon.server, daemon)
	daemonpb.RegisterTransferServiceServer(daemon.server, daemon)
	daemon.log.Debug().Msg("daemon services registered")

	// Get the cert for the daemon
	daemon.cert, err = daemon.getCert()
	if err != nil {
		daemon.log.Error().Err(err).Msg("couldn't get certificate")
		return nil, err
	}

	return daemon, nil
}

// Run runs the daemon until either the context is cancelled, or an error occurs.
// It returns ErrRestart if it stopped for a restart.
func (d *Daemon) Run(ctx context.Context) error {
	if !d.Running.CompareAndSwap(false, true) {
		return fmt.Errorf("daemon already running")
	}
	defer d.Running.Store(false)

	// Reset error state
	d.err = nil

	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	d.ctx, d.cancel = ctx, cancel
	defer cancel()
	// The registration is kept until the relay has finished its calls, so
	// that the answer to an orchestrator's call that stops the daemon, like
	// Restart, reaches it before it drops this daemon and its connection here
	regCtx, regCancel := context.WithCancel(context.WithoutCancel(ctx))
	d.regCtx = regCtx
	defer regCancel()

	// Join the network (without a VPN, this is the host network), unless one
	// was given
	var err error
	if d.network == nil {
		d.network, err = network.NewServer(ctx, d.Hostname, d.netAuth)
		if err != nil {
			d.log.Error().Err(err).Msg("couldn't join network")
			return err
		}
	}
	defer d.network.Close()
	// Get the local address of this daemon on the network
	d.setLocalAddr()
	// Create the main network listener that the relay will be served on; it
	// has an open ACL so remote entities are provided AuthCode ExternalCode
	// when in UNLOCKED state
	acl := listener.NewAcl(nil, nil, true)
	if d.Config.Daemon.Orchestrator != "" {
		if err = d.policy.SafeTransit(LockedState); err != nil {
			d.log.Error().Err(err).Msg("couldn't lock daemon")
			return err
		}
		ips, err := d.network.Resolve(ctx, d.orchestratorHost())
		if err != nil {
			d.log.Error().Err(err).Str("orchestrator", d.Config.Daemon.Orchestrator).
				Msg("couldn't resolve orchestrator host")
			return err
		}
		for _, ip := range ips {
			err = acl.AddIp(ip.String(), listener.AdminCode)
			if err != nil {
				d.log.Error().Err(err).Str("address", ip.String()).
					Msg("failed to add orchestrator IP to ACL")
				return err
			}
		}
		d.log.Info().Str("orchestrator", d.Config.Daemon.Orchestrator).
			Msg("daemon locked to orchestrator")
	}
	// Host on the configured port
	ln, err := d.network.Listen("tcp", d.Config.Daemon.Port)
	if err != nil {
		d.log.Error().Err(err).Int("port", d.Config.Daemon.Port).
			Msg("failed to create network listener")
		return err
	}
	netLn := listener.NewCodedListener(ln, acl, listener.WithLogger(d.log))
	d.log.Debug().Msg("network listener configured")

	// Host the control socket, which is the endpoint for local tools like `eagle`
	// to connect to the daemon
	path := d.socketPath
	if path == "" {
		path = util.GetDaemonSocketPath()
	}
	os.Remove(path) // remove the path so we can host a new socket
	ln, err = net.Listen("unix", path)
	if err != nil {
		d.log.Error().Err(err).Str("path", path).
			Msg("couldn't listen on control socket path")
		return err
	}
	ctlLn := listener.NewOwnerListener(ln, listener.PrivilegedCode, d.log)
	d.log.Debug().Msg("control listener configured")

	// Create an internal channel to internal services, routed through the
	// relay server
	sLn := listener.NewLocalListener(listener.AdminCode)
	conn, err := grpc.NewClient(
		"passthrough:///local",
		grpc.WithContextDialer(sLn.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		d.log.Error().Err(err).
			Msg("couldn't set up in-memory channel to internal services")
		return err
	}
	// Add header routes for calls targeting this daemon
	d.router.AddHeaderRoute(d.Hostname, conn)
	d.router.AddHeaderRoute(d.netAddr.String(), conn)
	// If no header is set, check service headers
	d.router.AddServiceRoute(daemonpb.DaemonService_ServiceDesc.ServiceName, conn)
	d.router.AddServiceRoute(daemonpb.TransferService_ServiceDesc.ServiceName, conn)
	// Calls routed here by this daemon's IP, as an orchestrator does, are for
	// its own services
	d.router.AddHeaderRoute(d.netAddr.String(), conn)
	d.log.Debug().Msg("router configured")

	// Populate services; a daemon whose services can't be set up, like when a
	// package isn't installed, runs without them, as when they fail to start
	if err := d.populateServices(); err != nil {
		d.svcMu.Lock()
		d.services, d.lookup = nil, make(map[string]*daemonService)
		d.svcMu.Unlock()
		d.err = fmt.Errorf("failed to set up services: %v", err)
		d.log.Error().Err(err).Msg("couldn't populate services")
	}

	// Register with orchestrator daemon, if applicable
	if err = d.register(); err != nil {
		d.log.Error().Err(err).Msg("couldn't establish initial connection to orchestrator")
		return err
	}

	// Start services, unless they couldn't be set up. Startup errors are kept
	// in d.err, and not returned from Run, since the daemon keeps running.
	if d.err == nil {
		if err := d.startServices(); err != nil { // there was an error, start in safe mode (no services)
			d.shutdownAll()
			d.err = err
			d.log.Error().Err(err).Msg("failed to start services")
		} else if err := d.startComputeServer(); err != nil { // no error, proceed to start compute server
			d.shutdownAll()
			d.err = fmt.Errorf("failed to start compute server: %v", err)
			d.log.Error().Err(err).Msg("failed to start compute server")
		} else {
			d.log.Info().Msg("daemon services started")
		}
	}

	// Serve listeners on relay server
	errChan := make(chan error, 3)
	go func() {
		errChan <- d.server.Serve(sLn)
	}()
	go func() {
		errChan <- d.relay.Serve(netLn)
	}()
	go func() {
		errChan <- d.relay.Serve(ctlLn)
	}()
	d.log.Info().Msgf("hosting daemon as %s (%s)", d.Hostname, d.netAddr.String())

	// Wait for the context to be cancelled or for an error
	select {
	case <-ctx.Done():
		d.log.Info().Msg("shutting down")
	case err = <-errChan:
		d.log.Error().Err(err).Msg("internal server exited with error, shutting down")
	}

	// Cancellation procedure
	cancel()
	d.stopComputeServer()
	d.shutdownAll()
	d.closeRemotes()
	d.relay.GracefulStop()
	// Cancel the registration context
	regCancel()
	d.regWg.Wait()
	conn.Close()
	d.server.GracefulStop()
	sLn.Close()
	if err == nil && d.restarting.Load() {
		return ErrRestart
	}
	return err
}

// shutdownAll shuts down all daemon service plugins/vehicles.
func (d *Daemon) shutdownAll() {
	d.svcMu.Lock()
	defer d.svcMu.Unlock()
	for _, s := range slices.Backward(d.services) {
		d.router.RemoveHeaderRoute(s.name)
		if p, ok := d.plugins[s.name]; ok {
			closePlugin(p)
		}
	}
}
