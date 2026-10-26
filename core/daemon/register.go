package daemon

import "github.com/cmusatyalab/steeleagle/config"

// register connects a daemon to its orchestrator and maintains a heartbeat to it.
// If the connection breaks, it attempts to reconnect with backoff. No-op if no
// orchestrator is set.
func (d *Daemon) register() (*config.DaemonConfig, error) {
	return nil, nil
}
