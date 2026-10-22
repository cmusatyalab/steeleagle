package daemon

import (
	_ "embed"
	"net/netip"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
)

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the control law for the daemon.

//go:embed defaults/config.toml
var DefaultConfig []byte // DefaultConfig is written as the config if none exists.

// Name of the daemon config file within the data director.y
const ConfigFileName = "config.toml"

// Hostname used if none is provided in the daemon config.
const DefaultHostname = "eagled"

// Law state entered when the daemon is managed by an orchestrator.
const LockedState = "LOCKED"

// Directory within the package directory holding the pending copy of the
// packages, which replaces the package directory on restart.
const PendingDirName = ".pending"

// Name of the metadata file stored in each installed package.
const PackageInfoFileName = ".package.toml"

// Prefix of temporary directories in the package directory.
const tmpPrefix = ".tmp-"

// Timeout for each git ls-remote probe when resolving a package repository.
const gitLsRemoteTimeout = 30 * time.Second

// Suffix of the plugin files at the root of a package; the plugin name is the
// file name without it.
const PluginFileSuffix = ".plugin.toml"

// Environment variables passed to every plugin: the name of the plugin to run
// within its package, and its args from the daemon config as a JSON object.
const (
	PluginNameEnv = "STEELEAGLE_PLUGIN"
	PluginArgsEnv = "STEELEAGLE_PLUGIN_ARGS"
)

// Environment variable passed to engines, naming the iceoryx service they
// serve on.
const IceoryxServiceEnv = "ICEORYX_SERVICE"

// Timeout for the orchestrator to answer a registration.
const orchestratorTimeout = 30 * time.Second

// Registration with the orchestrator: how long vehicles wait for the first
// registration before starting without remote compute, how often heartbeats
// are sent on the registration stream, how long either side waits for the
// other before the stream is dead, and the bounds of the backoff between
// attempts to register. They are variables so that tests can shorten them.
var (
	registerWait       = 10 * time.Second
	heartbeatInterval  = 5 * time.Second
	heartbeatTimeout   = 15 * time.Second
	registerBackoffMin = time.Second
	registerBackoffMax = 30 * time.Second
)

// Timeout for each remote daemon to list its services, when an orchestrator
// lists the services of its remote daemons.
const remoteListTimeout = 5 * time.Second

// Address that a daemon without an orchestrator finds the route to, to learn
// its own address from its default route. It is in TEST-NET-1, so no traffic
// is ever sent to it.
var defaultRouteProbe = netip.MustParseAddr("192.0.2.1")

// startOrder is the order in which service categories are started; services
// are stopped in reverse.
var startOrder = []daemonpb.ServiceCategory{
	daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA,
}

// categories describes how the services of each category are run.
var categories = map[daemonpb.ServiceCategory]categoryInfo{
	daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR: {name: "simulator", pluginType: "simulator", dir: "simulators"},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:    {name: "engine", pluginType: "engine", dir: "engines", restartable: true},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:   {name: "vehicle", pluginType: "driver", dir: "vehicles", restartable: true},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR:   {name: "monitor", pluginType: "monitor", dir: "monitors", restartable: true},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA:     {name: "extra", pluginType: "extra", dir: "extras"},
}

// Names of the local compute service cert and key files within its identity
// directory, as Uriel expects them, the name Uriel clients connect with,
// and how long a generated cert is valid.
const (
	LcsCertFileName = "certificate.der"
	LcsKeyFileName  = "key.der"
	lcsServerName   = "uriel"
	lcsCertValidity = 10 * 365 * 24 * time.Hour
)

// Directory within the data directory where the local compute service's
// Uriel server keeps its cert and key, and the host it binds on.
const (
	LcsIdentityDirName = "lcs"
	lcsBindHost        = "0.0.0.0"
)

// Metadata key that the relay records the caller address in, for the daemon's
// own services.
const callerHeader = "x-caller-addr"
