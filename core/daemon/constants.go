package daemon

import (
	_ "embed"
	"errors"
	"net/netip"
	"time"
)

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the control law for the daemon.

//go:embed defaults/config.toml
var DefaultConfig []byte // DefaultConfig is written as the config if none exists.

// ErrRestart is returned by Run when the daemon stopped for a restart, after a
// Restart or Configure call, so that its supervisor starts it again.
var ErrRestart = errors.New("daemon restart requested")

// ConfigFileName is the ame of the daemon config file within the config directory.
const ConfigFileName = "config.toml"

// DefaultHostname is used if none is provided in the daemon config.
const DefaultHostname = "eagled"

// SimulatorName is the name used for the simulator service.
const SimulatorName = "simulator"

// LockedState is the law state entered when the daemon is managed by an orchestrator.
const LockedState = "LOCKED"

// PackageUrlFileName is the name of the file at the root of each installed
// package holding the url it was installed from.
const PackageUrlFileName = ".url"

// PendingRemovePrefix starts the name of a file in the pending directory that
// marks the package named by the rest of it for removal.
const PendingRemovePrefix = "remove."

// PluginFileSuffix is the suffix of the plugin files at the root of a package; the plugin
// name is the file name without it.
const PluginFileSuffix = ".plugin.toml"

// PluginRunDirName is the name of the run directory of a plugin, within the
// plugin directory of its service, where its sockets are made. It is short,
// since socket paths are limited to 107 bytes.
const PluginRunDirName = "run"

// Shim socket paths for simulated plugins.
const (
	ShimClientSock = "in.sock"
	ShimListenSock = "out.sock"
)

// Environment variables passed to every plugin: the name of the plugin to run
// within its package, and its args from the daemon config as a JSON object.
const (
	PluginNameEnv = "STEELEAGLE_PLUGIN"
	PluginArgsEnv = "STEELEAGLE_PLUGIN_ARGS"
	ModelNameEnv  = "STEELEAGLE_MODELS"
	FileNameEnv   = "STEELEAGLE_FILES"
)

// Environment variable passed to engines, naming the iceoryx service they
// serve on.
const IceoryxServiceEnv = "ICEORYX_SERVICE"

// Deadline is the default RPC deadline between daemons for DaemonService calls.
const Deadline = 1 * time.Second

// RestartDeadline is the RPC deadline for RestartService calls between
// daemons, which wait for the plugin to start listening, for up to its
// timeout (15s by default). It is a variable so it can be modified for
// testing.
var RestartDeadline = 20 * time.Second

// Registration deadlines, variables so they can be modified for testing.
var (
	RegisterWait       = 10 * time.Second
	HeartbeatInterval  = 5 * time.Second
	HeartbeatTimeout   = 15 * time.Second
	RegisterBackoffMin = time.Second
	RegisterBackoffMax = 30 * time.Second
)

// DefaultRouteProbe is an IP address used to get the daemon's own IP address
var DefaultRouteProbe = netip.MustParseAddr("8.8.8.8")

// Names of the local compute service cert and key files within its identity
// directory, as Uriel expects them, the name Uriel clients connect with,
// and how long a generated cert is valid.
const (
	LcsCertFileName = "certificate.der"
	LcsKeyFileName  = "key.der"
	LcsServerName   = "uriel"
	LcsCertValidity = 10 * 365 * 24 * time.Hour
	LcsBindHost     = "0.0.0.0"
)

// Metadata key that the relay records the caller address in, for the daemon's
// own services.
const callerHeader = "x-caller-addr"
