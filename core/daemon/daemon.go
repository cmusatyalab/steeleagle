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
	endpoint   string                   // iceoryx endpoint, for engines only
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
	rcsCert    string                                      // orchestrator remote compute service cert, if any
	selfAddr   netip.Addr                                  // address of this daemon as seen by the orchestrator, if registered
	certMu     sync.Mutex                                  // mutex to protect the local compute cert files
	remotes    map[netip.Addr]*grpc.ClientConn             // connections to registered remote daemons, by IP
	remotesMu  sync.Mutex                                  // mutex to protect remotes
	ctx        context.Context                             // context for the daemon
	cancel     context.CancelFunc                          // cancel function for active contexts
	log        zerolog.Logger                              // logger object
}

// Creates a new daemon from the config in the data directory.
func NewDaemon(options ...DaemonOption) (*Daemon, error) {
	daemon := &Daemon{
		log: zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(daemon)
	}

	// Locate and parse the config; a missing config is an error
	if daemon.configPath == "" {
		dataDir, err := util.GetDataDir()
		if err != nil {
			daemon.log.Error().Err(err).Str("directory", dataDir).
				Msg("unable to create or access daemon data directory")
			return nil, err
		}
		daemon.configPath = filepath.Join(dataDir, ConfigFileName)
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

// Runs the daemon, blocking until the provided context is canceled or the
// relay exits with an error.
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
	// AuthCode ExternalCode; however, a daemon with an orchestrator adds an admin
	// IP for its orchestrator and locks external codes from write access
	acl := listener.NewAcl(nil, nil, true)
	if d.Config.Daemon.Orchestrator != "" {
		if err = d.addOrchestratorToAcl(ctx, acl); err != nil {
			d.log.Error().Err(err).Str("orchestrator", d.Config.Daemon.Orchestrator).
				Msg("could not resolve orchestrator")
			return err
		}
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

	// Serve until the relay exits or the context is canceled; the server
	// stops on its own once its listener closes
	go d.server.Serve(d.serverLn)
	errChan := make(chan error, 1)
	go func() {
		errChan <- d.relay.Serve(d.netLn)
	}()
	d.log.Info().Int("port", d.Config.Daemon.Port).Msg("daemon started")

	// Gather services, then register vehicles with the orchestrator, which
	// provides the remote compute service the vehicles are started with
	if err := d.gatherServices(); err != nil {
		d.log.Error().Err(err).Msg("could not set up some services")
	}
	if d.Config.Daemon.Orchestrator != "" {
		if err := d.registerWithOrchestrator(ctx); err != nil {
			d.log.Error().Err(err).Str("orchestrator", d.Config.Daemon.Orchestrator).
				Msg("could not register with orchestrator, starting vehicles without remote compute")
		}
	}
	if err := d.startServices(d.allServices()); err != nil {
		d.log.Error().Err(err).Msg("could not start some services")
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

	// Stop services before the relay, since plugins hold connections to it
	cancel()
	d.stopServices(d.allServices())
	d.closeRemotes()
	if !relayDone {
		d.relay.GracefulStop()
		<-errChan
	}
	// The relay has finished its calls, so none are left to the server
	d.serverConn.Close()
	d.server.GracefulStop()
	d.log.Info().Msg("shutdown complete")
	return err
}
