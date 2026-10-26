package daemon

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"net"
	"net/netip"
	"os"
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
	uriel "github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// service is a vehicle, engine, or generic service running on the daemon.
type service struct {
	name       string                   // name of the service
	category   daemonpb.ServiceCategory // service category (simulator, vehicle, engine, extra)
	uri        string                   // package uri for this service
	pluginName string                   // plugin file name
	config     *config.PluginConfig     // service plugin config
	ln         net.Listener             // listener for the plugin
	conn       *grpc.ClientConn         // gRPC connection to the plugin
	plugin     plugin.Plugin            // running plugin reference
	simulated  bool                     // whether or not the service belongs to the simulator
	cancel     context.CancelFunc       // cancel function to stop service
}

// Daemon is the SteelEagle daemon. It is responsible for orchestrating
// services based on a config.toml. The config.toml is located in the
// XDG config directory, which defaults to `~/.config`. The daemon can
// optionally be configured by using the command `eagle`.
type Daemon struct {
	daemonpb.UnimplementedDaemonServiceServer
	daemonpb.UnimplementedTransferServiceServer
	Config     *config.DaemonConfig // daemon config
	Running    atomic.Bool          // whether or not the daemon is currently running
	orchConfig *config.DaemonConfig // orchestrator daemon config, nil if no orchestrator
	policy     *policy.Policy       // policy for command authorization
	netAuth    string               // network auth key for this daemon (usually for VPNs)
	netAddr    netip.Addr           // local address of this daemon
	network    *network.Server      // network server object this
	connected  atomic.Bool          // whether or not the daemon is connected to its orchestrator
	router     *router.Router       // network router
	relay      *grpc.Server         // relay gRPC server reference
	server     *grpc.Server         // main gRPC server reference
	engines    map[string]*service  // engine services
	vehicles   map[string]*service  // vehicle services
	extras     map[string]*service  // extra services
	simulated  map[string]*service  // simulated services
	all        map[string]*service  // all services
	lcs        *uriel.Server        // local compute server reference
	cert       []byte               // DER cert for uriel
	restarting atomic.Bool          // whether or not the daemon is currently restarting
	srvMu      sync.RWMutex         // mutex for reading or writing services
	pkgMu      sync.RWMutex         // mutex for reading or writing packages to .pending
	ctx        context.Context      // context for the daemon
	cancel     context.CancelFunc   // cancel function for active contexts
	log        zerolog.Logger       // logger object
}

// Creates a new daemon from the config in the config directory.
func NewDaemon(options ...DaemonOption) (*Daemon, error) {
	daemon := &Daemon{
		log: zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(daemon)
	}

	// Parse the config or write a new one if it doesn't exist
	var err error
	configPath, err := util.GetConfigDir()
	if err != nil {
		daemon.log.Error().Err(err).Str("path", configPath).
			Msg("failed to get config directory")
		return nil, err
	}
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
		daemon.Config.Daemon.Hostname = DefaultHostname
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

	return daemon, nil
}

// Run runs the daemon until either the context is cancelled, or an error occurs.
func (d *Daemon) Run(ctx context.Context) error {
	if !d.Running.CompareAndSwap(false, true) {
		return fmt.Errorf("daemon already running")
	}
	defer d.Running.Store(false)

	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	d.ctx, d.cancel = ctx, cancel
	defer cancel()

	// Join the network (without a VPN, this is the host network)
	var err error
	d.network, err = network.NewServer(ctx, d.Config.Daemon.Hostname, d.netAuth)
	if err != nil {
		d.log.Error().Err(err).Msg("couldn't join network")
		return err
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
	path := util.GetDaemonSocketPath()
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
	d.router.AddServiceRoute(daemonpb.DaemonService_ServiceDesc.ServiceName, conn)
	d.router.AddServiceRoute(daemonpb.TransferService_ServiceDesc.ServiceName, conn)
	d.log.Debug().Msg("router configured")

	// Register with orchestrator daemon, if applicable
	d.orchConfig, err = d.register()
	if err != nil {
		d.log.Error().Err(err).Msg("couldn't establish initial connection to orchestrator")
		return err
	}
	d.log.Info().Msg("daemon connected to orchestrator")

	// Start services
	err = d.startServices()
	if err != nil {
		d.log.Error().Err(err).Msg("failed to start services")
		return err
	}
	d.log.Info().Msg("daemon services started")
	defer d.waitForTermination()

	// Start the local computer server
	d.startComputeServer()
	defer d.stopComputeServer()

	// Serve listeners on relay server
	errChan := make(chan error, 1)
	go func() {
		errChan <- d.server.Serve(sLn)
	}()
	go func() {
		errChan <- d.relay.Serve(netLn)
	}()
	go func() {
		errChan <- d.relay.Serve(ctlLn)
	}()
	d.log.Info().Msgf("hosting daemon as %s (%s)", d.Config.Daemon.Hostname, d.netAddr.String())
	defer d.relay.GracefulStop()
	defer d.server.GracefulStop()

	// Wait for the context to be cancelled or for an error
	select {
	case <-ctx.Done():
		d.log.Info().Msg("shutting down")
	case err = <-errChan:
		d.log.Error().Err(err).Msg("internal server exited with error, shutting down")
	}
	return nil
}

// waitForTermination waits on all daemon services to exit before returning.
func (d *Daemon) waitForTermination() {
	for _, s := range d.all {
		_ = s.plugin.Wait()
		if s.conn != nil {
			s.conn.Close()
		}
	}
}
