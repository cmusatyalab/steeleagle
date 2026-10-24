package daemon

import (
	_ "embed"
	"net/netip"
	"time"
)

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the control law for the daemon.

//go:embed defaults/config.toml
var DefaultConfig []byte // DefaultConfig is written as the config if none exists.

// ConfigFileName is the ame of the daemon config file within the config directory.
const ConfigFileName = "config.toml"

// DefaultHostname is used if none is provided in the daemon config.
const DefaultHostname = "eagled"

// LockedState is the law state entered when the daemon is managed by an orchestrator.
const LockedState = "LOCKED"

// PendingDirName is the directory within the package directory holding the pending
// copy of the packages, which replaces the package directory on restart.
const PendingDirName = ".pending"

// PackageInfoFilename is the name of the metadata file stored in each installed package.
const PackageInfoFileName = ".package.toml"

// PluginFileSuffix is the suffix of the plugin files at the root of a package; the plugin
// name is the file name without it.
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

// Deadline is the default RPC deadline between daemons for DaemonService calls.
const Deadline = 1 * time.Second

// Registration deadlines, variables so they can be modified for testing.
var (
	registerWait       = 10 * time.Second
	heartbeatInterval  = 5 * time.Second
	heartbeatTimeout   = 15 * time.Second
	registerBackoffMin = time.Second
	registerBackoffMax = 30 * time.Second
)

// defaultIp is the default IP for a daemon without an orchestrator
var defaultIp = netip.MustParseAddr("127.0.0.1")

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
