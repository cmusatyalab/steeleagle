package plugin

// The directory that plugin files are bound to within containers, and that
// script plugins and linked files are bound to within sandboxes, which bind
// package plugins at their own path
const bindDir string = "steeleagle"

// The executable and task that package plugins are started with (pixi run start)
const pixiExec string = "pixi"
const pixiRun string = "run"
const pixiStart string = "start"

// Manifests that mark a directory as a pixi package, in order of precedence
var pixiManifests = []string{"pixi.toml", "pyproject.toml"}

// Socket names for server/client
const clientSockName string = "out.sock"
const listenSockName string = "in.sock"

// Client socket environment variable names passed to the subprocess
const ClientSockEnv string = "STEELEAGLE_CLIENT_SOCKET"

// Listener socket environment variable names passed to the subprocess
const ListenSockEnv string = "STEELEAGLE_LISTEN_SOCKET"
