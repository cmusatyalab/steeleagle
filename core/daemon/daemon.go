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
	"sync"
	"sync/atomic"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/network"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"github.com/cmusatyalab/steeleagle/v4/core/vehicle"
	"github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type serviceInfo struct {
	name       string                   // service name, unique within its category
	category   daemonpb.ServiceCategory // service category
	pluginName string                   // name of the plugin within its package
	url        string                   // normalized package url
	config     *config.PluginConfig     // parsed .plugin.toml
	toml       []byte                   // raw .plugin.toml
	ln         net.Listener             // listener for calls from the plugin, if any
	conn       *grpc.ClientConn         // client connection to the plugin or vehicle, if any
	plugin     plugin.Plugin            // plugin, the driver for vehicles
	vehicle    *vehicle.Vehicle         // vehicle, for vehicles only
	started    time.Time                // start time of the current run
	cancel     context.CancelFunc       // stop the service, nil if not started
	err        error                    // why the service couldn\'t be set up, or why its last start failed
}

type Daemon struct {
	daemonpb.UnimplementedDaemonServiceServer
	daemonpb.UnimplementedTransferServiceServer
	Config     *config.DaemonConfig                        // daemon config
	RunDir     string                                      // path to daemon runtime directory
	PkgDir     string                                      // path to daemon package directory
	pkgMu      sync.Mutex                                  // mutex to protect package directory updates
	Running    atomic.Bool                                 // whether or not the daemon is currently running
	configPath string                                      // path to daemon config.toml
	authKey    string                                      // VPN auth key, if any
	policy     *policy.Policy                              // policy for command authorization
	router     *router.Router                              // router to external daemons/internal vehicles
	network    *network.Server                             // network server (VPN or host)
	netLn      net.Listener                                // main network listener
	relay      *grpc.Server                                // gRPC relay, which checks and routes every call
	server     *grpc.Server                                // in-process gRPC server for the daemon's own services
	serverLn   *listener.LocalListener                     // listener for the server
	serverConn *grpc.ClientConn                            // router connection to the server
	pluginOut  io.Writer                                   // output of plugin processes, stdout if nil
	services   map[daemonpb.ServiceCategory][]*serviceInfo // available services, in config order
	svcMu      sync.Mutex                                  // mutex to protect services
	rcsAddr    string                                      // orchestrator remote compute service address, if any
	rcsCert    []byte                                      // orchestrator remote compute service cert in DER, if any
	rcsEngines map[string]config.EngineCap                 // engines of the orchestrator remote compute service by qualified name, if any
	rcsMu      sync.Mutex                                  // mutex to protect the orchestrator remote compute service, which changes on each registration
	selfAddr   netip.Addr                                  // address of this daemon on the network, which qualifies service names
	certMu     sync.Mutex                                  // mutex to protect the local compute cert files
	remotes    map[netip.Addr]*remoteInfo                  // registered remote daemons, by IP
	remotesMu  sync.Mutex                                  // mutex to protect remotes
	uriel      *uriel.Server                               // local compute service, if started
	ctx        context.Context                             // context for the daemon
	cancel     context.CancelFunc                          // cancel function for active contexts
	restart    atomic.Bool                                 // whether the daemon is stopping for a restart
	log        zerolog.Logger                              // logger object
}

// Creates a new daemon from the config in the config directory.
func NewDaemon(options ...DaemonOption) (*Daemon, error) {
	daemon := &Daemon{
		log: zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(daemon)
	}

	// Locate and parse the config; a missing config is an error
	if daemon.configPath == "" {
		configDir, err := util.GetConfigDir()
		if err != nil {
			daemon.log.Error().Err(err).Str("directory", configDir).
				Msg("unable to create or access daemon config directory")
			return nil, err
		}
		daemon.configPath = filepath.Join(configDir, ConfigFileName)
	}
	if _, err := os.Stat(daemon.configPath); errors.Is(err, fs.ErrNotExist) {
		daemon.log.Warn().Str("path", daemon.configPath).
			Msg("no daemon config found, using default")
		if err := daemon.writeConfig(DefaultConfig); err != nil {
			daemon.log.Error().Err(err).Str("path", daemon.configPath).
				Msg("could not write default daemon config")
			return nil, err
		}
	} else if err != nil {
		daemon.log.Error().Err(err).Str("path", daemon.configPath).
			Msg("could not access daemon config")
		return nil, err
	}
	var err error
	daemon.Config, err = config.ParseDaemonConfigFromFilepath(daemon.configPath)
	if err != nil {
		daemon.log.Error().Err(err).Str("path", daemon.configPath).
			Msg("could not parse daemon config")
		return nil, err
	}
	if err := daemon.Config.ValidateServices(); err != nil {
		daemon.log.Error().Err(err).Str("path", daemon.configPath).
			Msg("invalid daemon config, using default")
		daemon.Config, err = config.ParseDaemonConfigFromBytes(DefaultConfig)
		if err != nil {
			daemon.log.Error().Err(err).Msg("could not parse default daemon config")
			return nil, err
		}
	}
	if daemon.Config.Daemon.Hostname == "" {
		daemon.Config.Daemon.Hostname = DefaultHostname
	}
	daemon.log.Debug().Str("path", daemon.configPath).Msg("daemon config loaded")

	// Set directory paths
	daemon.RunDir, err = util.GetDaemonRunDir()
	if err != nil {
		daemon.log.Error().Err(err).Str("directory", daemon.RunDir).
			Msg("unable to create daemon runtime directory")
		return nil, err
	}
	daemon.log.Debug().Str("directory", daemon.RunDir).
		Msg("daemon runtime directory configured")
	daemon.PkgDir, err = util.GetPackageDir("")
	if err != nil {
		daemon.log.Error().Err(err).Str("directory", daemon.PkgDir).
			Msg("unable to create or access daemon package directory")
		return nil, err
	}
	daemon.log.Debug().Str("directory", daemon.PkgDir).
		Msg("daemon package directory configured")

	// Apply package installs and removals made since the last start
	if err := daemon.commitPendingPackages(); err != nil {
		daemon.log.Error().Err(err).Str("directory", daemon.PkgDir).
			Msg("could not apply pending packages")
		return nil, err
	}

	// Policy and law setup
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		daemon.log.Error().Err(err).Msg("could not parse law")
		return nil, err
	}
	daemon.policy, err = policy.NewPolicy(law, policy.WithLogger(daemon.log))
	if err != nil {
		daemon.log.Error().Err(err).Msg("could not create policy")
		return nil, err
	}

	// Set up the router, relay and server
	if err := daemon.setupRelay(); err != nil {
		daemon.log.Error().Err(err).Msg("could not set up relay")
		return nil, err
	}

	return daemon, nil
}

// ErrRestart is returned by Run when the daemon stopped for a restart, after
// a Restart or Configure call, so that the caller exits for its supervisor
// (systemd) to start the daemon again.
var ErrRestart = errors.New("daemon restart requested")

// Runs the daemon, blocking until the provided context is canceled, the relay
// exits with an error, or the daemon is stopped for a restart. Everything the
// daemon started is closed by the time it returns.
func (d *Daemon) Run(ctx context.Context) (err error) {
	if !d.Running.CompareAndSwap(false, true) {
		return fmt.Errorf("daemon already running")
	}
	defer d.Running.Store(false)

	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	d.ctx, d.cancel = ctx, cancel
	defer cancel()

	// Join the network; under the notailscale build tag this is the host network
	d.log.Info().Str("hostname", d.Config.Daemon.Hostname).Bool("vpn", network.Tailscale).
		Msg("joining network")
	d.network, err = network.NewServer(ctx, d.Config.Daemon.Hostname, d.authKey)
	if err != nil {
		d.log.Error().Err(err).Msg("could not join network")
		return err
	}
	defer d.network.Close()

	// The main network listener has an open ACL so remote entities not on it get
	// AuthCode ExternalCode; however, a daemon with an orchestrator locks
	// external codes from write access, and its orchestrator's IPs get AdminCode
	// once they are resolved, which registering retries until they are
	acl := listener.NewAcl(nil, nil, true)
	if d.Config.Daemon.Orchestrator != "" {
		if err = d.policy.SafeTransit(LockedState); err != nil {
			d.log.Error().Err(err).Msg("could not lock daemon")
			return err
		}
		d.log.Info().Str("orchestrator", d.Config.Daemon.Orchestrator).
			Msg("daemon locked to orchestrator")
	}
	ln, err := d.network.Listen("tcp", d.Config.Daemon.Port)
	if err != nil {
		d.log.Error().Err(err).Int("port", d.Config.Daemon.Port).
			Msg("failed to create network listener")
		return err
	}
	d.netLn = listener.NewCodedListener(ln, acl, listener.WithLogger(d.log))

	// The control socket is how local tools, like the eagle CLI, call the
	// daemon; only its own user can connect, and is privileged, so that the
	// law still applies to them
	ctlLn, err := d.listenControl()
	if err != nil {
		d.log.Error().Err(err).Str("path", util.GetDaemonSocketPath()).
			Msg("failed to create control socket listener")
		d.netLn.Close()
		return err
	}

	// Service names are qualified with the daemon's address, so they are
	// unique across the network
	d.selfAddr = d.localAddr(ctx)
	d.log.Info().Str("address", d.selfAddr.String()).Msg("daemon address found")

	// Serve until the relay exits or the context is canceled; the server
	// stops on its own once its listener closes
	go d.server.Serve(d.serverLn)
	errChan := make(chan error, 1)
	go func() {
		errChan <- d.relay.Serve(d.netLn)
	}()
	// The control socket stops with the relay
	go func() {
		if err := d.relay.Serve(ctlLn); err != nil {
			d.log.Error().Err(err).Msg("control socket exited with error")
		}
	}()
	d.log.Info().Int("port", d.Config.Daemon.Port).Msg("daemon started")

	// Gather services, then keep the vehicles registered with the orchestrator,
	// which provides the remote compute service the vehicles are started with;
	// vehicles wait for the first registration for up to registerWait
	if err := d.gatherServices(); err != nil {
		d.log.Error().Err(err).Msg("could not set up some services")
	}
	var registering sync.WaitGroup
	if d.Config.Daemon.Orchestrator != "" {
		// Calls the orchestrator routes here by this daemon's IP are for its
		// own services; the route is added first, so that none are rejected
		// once the orchestrator has the route back here
		d.router.AddHeaderRoute(d.selfAddr.String(), d.serverConn)
		r := newRegistration(acl)
		registering.Go(func() { d.maintainRegistration(ctx, r) })
		select {
		case <-r.registered:
		case <-ctx.Done():
		case <-time.After(registerWait):
			d.log.Warn().Str("orchestrator", d.Config.Daemon.Orchestrator).
				Msg("not registered with orchestrator yet, starting vehicles without remote compute")
		}
	}
	if err := d.startServices(d.selectServices((*serviceInfo).setUp)); err != nil {
		d.log.Error().Err(err).Msg("could not start some services")
	}
	if err := d.startUrielServer(); err != nil {
		d.log.Error().Err(err).Int("port", d.Config.Daemon.Lcs).
			Msg("could not start local compute service")
	}

	relayDone := false
	select {
	case <-ctx.Done():
		d.log.Info().Msg("context canceled, shutting down")
	case err = <-errChan:
		relayDone = true
		if err != nil {
			d.log.Error().Err(err).Msg("relay exited with error, shutting down")
		}
	}

	// Stop services before the relay, since plugins hold connections to it;
	// registration streams end with the daemon context
	cancel()
	registering.Wait()
	d.stopUrielServer()
	d.stopServices(d.selectServices(nil))
	d.closeServices()
	d.closeRemotes()
	if !relayDone {
		d.relay.GracefulStop()
		<-errChan
	}
	// The relay has finished its calls, so none are left to the server
	d.serverConn.Close()
	d.server.GracefulStop()
	d.log.Info().Msg("shutdown complete")
	if err == nil && d.restart.Load() {
		err = ErrRestart
	}
	return err
}

// listenControl listens on the daemon's control socket, replacing any left by
// a daemon that didn't stop cleanly. Only the daemon's own user can connect,
// as AuthCode PrivilegedCode.
func (d *Daemon) listenControl() (net.Listener, error) {
	path := util.GetDaemonSocketPath()
	if err := os.Remove(path); err != nil && !errors.Is(err, fs.ErrNotExist) {
		return nil, err
	}
	ln, err := net.Listen("unix", path)
	if err != nil {
		return nil, err
	}
	if err := os.Chmod(path, 0o600); err != nil {
		ln.Close()
		return nil, err
	}
	d.log.Debug().Str("path", path).Msg("control socket listening")
	return listener.NewOwnerListener(ln, listener.PrivilegedCode, d.log), nil
}

// localAddr returns the address of this daemon on the network: the one it
// reaches its orchestrator from, if it has one, or else the one its default
// route uses. If neither can be found, as on a daemon without a network, it is
// the loopback address.
func (d *Daemon) localAddr(ctx context.Context) netip.Addr {
	remote := defaultRouteProbe
	if d.Config.Daemon.Orchestrator != "" {
		host := d.Config.Daemon.Orchestrator
		if h, _, err := net.SplitHostPort(host); err == nil {
			host = h
		}
		if addrs, err := d.network.Resolve(ctx, host); err == nil {
			remote = addrs[0]
		}
	}
	addr, err := d.network.LocalAddr(ctx, remote)
	if err != nil {
		d.log.Warn().Err(err).Msg("could not find daemon address, using loopback")
		return netip.AddrFrom4([4]byte{127, 0, 0, 1})
	}
	return addr
}

// qualify returns name qualified with the daemon's address, as "{daemon
// IP}.{name}", so that it is unique across the network. An empty name, or
// any name before the daemon has an address, is returned as it is.
func (d *Daemon) qualify(name string) string {
	if name == "" || !d.selfAddr.IsValid() {
		return name
	}
	return d.selfAddr.String() + "." + name
}
