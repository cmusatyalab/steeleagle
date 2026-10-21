package daemon

import (
	_ "embed"
	"time"
)

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the control law for the daemon.

// Name of the daemon config file within the data directory
const ConfigFileName = "config.toml"

// Hostname used if none is provided in the daemon config
const DefaultHostname = "eagled"

// Law state entered when the daemon is managed by an orchestrator
const LockedState = "LOCKED"

// Directory within the package directory holding the pending copy of the
// packages, which replaces the package directory on restart
const PendingDirName = ".pending"

// Name of the metadata file stored in each installed package
const PackageInfoFileName = ".package.toml"

// Marker file in the pending directory, written when it changes
const dirtyFileName = ".dirty"

// Prefix of temporary directories in the package directory
const tmpPrefix = ".tmp-"

// Timeout for each git ls-remote probe when resolving a package repository
const gitLsRemoteTimeout = 30 * time.Second
