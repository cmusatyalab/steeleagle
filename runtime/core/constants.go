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

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law can be found.

//go:embed defaults/check.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.
