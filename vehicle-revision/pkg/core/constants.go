package core

import "embed"

// Default port to use if no port is specified.
const DefaultPort int = 50000

// Default driver UDS socket name
const DriverSocket string = "driver.sock"

// Default mission UDS socket name
const MissionSocket string = "mission.sock"

// Default input and output data XPUB/XSUB socket names
const FrontendDataSocket string = "datain.sock"
const BackendDataSocket string = "dataout.sock"

// Runtime directory is the base filepath to all runtime data.
const RuntimeDirectory string = "/var/run/"

// ApplicationName is the base folder name to use within the user's config directory for all config files.
const ApplicationName string = "steeleagle"

// LawFilename is the expected name of the law config file within the user's config directory
const LawFilename string = "laws.toml"

// RegoFilename is the expected name of the Rego OPA config file within the user's config directory
const RegoFilename string = "auth.rego"

// BwrapArgsFilename is the expected name of the Bubblewrap args file within the user's config directory
const BwrapArgsFilename string = "bwrap.args"

//go:embed ../../configs/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law can be found.

//go:embed ../../configs/config.toml
var DefaultConfig []byte // DefaultConfig is the default daemon config if no user-specified config can be found.

//go:embed ../../configs/policy.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.

//go:embed ../../configs/bwrap.args
var DefaultBwrapArgs string // DefaultBwrapArgs is the default arg file for Bubblewrap sandboxing.
