package vehicle

import _ "embed"

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law is provided.

// Socket path for main services
const (
	MainSocketName = "main"
)

// Service name for mission
const (
	MissionServiceName = "steeleagle_protocol.v1.services.mission.MissionService"
)
