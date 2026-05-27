package util

// Used by the authentication interceptor to map process IDs
// to named modules in the system; these codes are then checked
// within the law file for permissions (e.g. the mission module
// calling Hold would map to mission.Hold)
type AuthCode string

const (
	ServerCode   AuthCode = "server"
	AdminCode    AuthCode = "admin"
	MissionCode  AuthCode = "mission"
	ExternalCode AuthCode = "external"
	UnknownCode  AuthCode = "unknown"
)

// The run hook that processes are started from within containers
const runhook string = "main"

// Used to determine how to run a plugin
type PluginRuntime string

const (
	Process   PluginRuntime = "Process"
	Container PluginRuntime = "Container"
	Sandbox   PluginRuntime = "Sandbox"
)
