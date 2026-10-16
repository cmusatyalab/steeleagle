package plugin

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
