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

// Directories where the runtime files live
const runtimeDir string = "steeleagle"
const vehicleDir string = "vehicles"
const pluginDir string = "plugins"

// The run hook that processes are started from within containers
const bindDir string = "steeleagle"
const runHook string = "run.sh"

// Environment variable names passed to the subprocess
const ClientSockEnv string = "CLIENT_SOCKET"
const ListenSockEnv string = "LISTEN_SOCKET"

// Used to determine how to run a plugin
type PluginRuntime string

const (
	Process   PluginRuntime = "Process"
	Container PluginRuntime = "Container"
	Sandbox   PluginRuntime = "Sandbox"
)
