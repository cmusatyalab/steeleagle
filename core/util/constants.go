package util

// Used by the authentication interceptor to map process IDs
// to named modules in the system; these codes are then checked
// within the law file for permissions (e.g. the mission module
// calling Hold would map to mission.Hold)
type AuthCode int

const (
	ServerCode AuthCode = iota
	AdminCode
	MissionCode
	ExternalCode
	UnknownCode
)

// Converts an AuthCode to its string representation.
func (c AuthCode) String() string {
	switch c {
	case ServerCode:
		return "server"
	case AdminCode:
		return "admin"
	case MissionCode:
		return "mission"
	case ExternalCode:
		return "external"
	default:
		return "unknown"
	}
}

// Directories where the runtime files live
const projectDir string = "steeleagle"
const vehicleDir string = "vehicles"
const pluginDir string = "plugins"

// Directory where installed plugins live, one subdirectory per category
// (e.g. "driver", "mission", "extra")
const installedPluginDir string = "plugins"

// The run hook that processes are started from within containers
const bindDir string = "steeleagle"
const runHook string = "run.sh"

// Socket names for server/client
const clientSockName string = "out.sock"
const listenSockName string = "in.sock"

// Client socket environment variable names passed to the subprocess
const ClientSockEnv string = "CLIENT_SOCKET"

// Listener socket environment variable names passed to the subprocess
const ListenSockEnv string = "LISTEN_SOCKET"
