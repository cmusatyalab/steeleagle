package vehicle

import _ "embed"

// Used by the authentication interceptor to map process IDs
// to named modules in the system; these codes are then checked
// within the law file for permissions (e.g. the mission module
// calling Hold would map to mission.Hold)
type AuthCode string

const (
	Server  AuthCode = "server"
	Kernel  AuthCode = "kernel"
	Driver  AuthCode = "driver"
	Mission AuthCode = "mission"
	Extra   AuthCode = "extra"
	Unknown AuthCode = "unknown"
)

// Script within a plugin package that runs the plugin
const PluginRunScript string = "run.sh"

// Default port to use if no port is specified.
const DefaultPort int = 50000

// Default main services socket name
const MainSocket string = "services.sock"

// ApplicationName is the base folder name to use within the user's config directory for all config files.
const ApplicationName string = "steeleagle"

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law can be found.

//go:embed defaults/check.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.
