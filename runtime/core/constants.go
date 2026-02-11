package core

import _ "embed"

// Default port to use if no port is specified.
const DefaultPort int = 50000

// Default main services socket name
const MainSocket string = "services.sock"

// Default control UDS socket name
const ControlSocket string = "control.sock"

// Default mission UDS socket name
const MissionSocket string = "mission.sock"

// Default input and output data XPUB/XSUB socket names
const DataInSocket string = "datain.sock"
const DataOutSocket string = "dataout.sock"

// ApplicationName is the base folder name to use within the user's config directory for all config files.
const ApplicationName string = "steeleagle"

// LawFilename is the expected name of the law config file within the user's config directory
const LawFilename string = "laws.toml"

// RegoFilename is the expected name of the Rego OPA config file within the user's config directory
const RegoFilename string = "policy.rego"

// BwrapArgsFilename is the expected name of the Bubblewrap args file within the user's config directory
const BwrapArgsFilename string = "bwrap.args"

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law can be found.

//go:embed defaults/config.toml
var DefaultConfig []byte // DefaultConfig is the default daemon config if no user-specified config can be found.

//go:embed defaults/policy.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.

//go:embed defaults/bwrap.args
var DefaultBwrapArgs string // DefaultBwrapArgs is the default arg file for Bubblewrap sandboxing.
