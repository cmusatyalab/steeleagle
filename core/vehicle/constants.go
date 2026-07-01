package vehicle

import _ "embed"

// Default port to use if no port is specified.
const DefaultPort int = 50000

// MainSocketName is the name for the main services socket.
const MainSocketName string = "main"

// AdminSocketName is the name for the admin services socket.
const AdminSocketName string = "admin"

// MainListenerName is the listener name for the main listener displayed in logs.
const MainListenerName string = "main"

// AdminListenerName is the listener name for the admin listener displayed in logs.
const AdminListenerName string = "admin"

// MissionListenerName is the listener name for the mission listener displayed in logs.
const MissionListenerName string = "mission"

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law is provided.

//go:embed defaults/check.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.
