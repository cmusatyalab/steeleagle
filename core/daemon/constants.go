package daemon

import (
	_ "embed"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
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

// Marker file in the pending directory, written when it changes.
const dirtyFileName = ".dirty"

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

// Timeout for registering with the orchestrator.
const orchestratorTimeout = 30 * time.Second

// startOrder is the order in which service categories are started; services
// are stopped in reverse.
var startOrder = []daemonpb.ServiceCategory{
	daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_COMMANDER,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR,
	daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA,
}

// categories is the mapping from ServiceCategory to TOML field.
var categories = map[daemonpb.ServiceCategory]categoryInfo{
	daemonpb.ServiceCategory_SERVICE_CATEGORY_SIMULATOR: {"simulator", "simulators", listener.ExternalCode},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE:    {"engine", "engines", listener.ExternalCode},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE:   {"driver", "vehicles", listener.UnknownCode},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_COMMANDER: {"commander", "commanders", listener.PrivilegedCode},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_MONITOR:   {"monitor", "monitors", listener.ExternalCode},
	daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA:     {"extra", "extras", listener.UnknownCode},
}

// Names of the local compute service cert and key files within the data
// directory, and how long a generated cert is valid.
const (
	LcsCertFileName = "lcs.crt"
	LcsKeyFileName  = "lcs.key"
	lcsCertValidity = 10 * 365 * 24 * time.Hour
)
