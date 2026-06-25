package vehicle

import _ "embed"

// Default port to use if no port is specified.
const DefaultPort int = 50000

// Default main services socket name
const MainSocket string = "services"

const AdminSocket string = "admin"

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law can be found.

//go:embed defaults/check.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.
