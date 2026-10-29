package daemon

import (
	"github.com/cmusatyalab/steeleagle/v4/core/util/network"
	"github.com/rs/zerolog"
)

type DaemonOption func(*Daemon)

// WithLogger sets a custom logger object for the daemon.
func WithLogger(logger zerolog.Logger) DaemonOption {
	return func(d *Daemon) {
		d.log = logger
	}
}

// WithConfigPath sets the path of the daemon config, instead of config.toml in
// the config directory.
func WithConfigPath(path string) DaemonOption {
	return func(d *Daemon) {
		d.configPath = path
	}
}

// WithNetwork sets the network the daemon runs on, instead of joining one
// when it runs.
func WithNetwork(n network.Network) DaemonOption {
	return func(d *Daemon) {
		d.network = n
	}
}

// WithSocketPath sets the path of the daemon's control socket, instead of the
// one in the runtime directory.
func WithSocketPath(path string) DaemonOption {
	return func(d *Daemon) {
		d.socketPath = path
	}
}

// WithoutLogServer stops the daemon from serving its logs through logdy,
// which can only run once per process.
func WithoutLogServer() DaemonOption {
	return func(d *Daemon) {
		d.noLogServer = true
	}
}
