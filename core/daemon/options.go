package daemon

import "github.com/rs/zerolog"

type DaemonOption func(*Daemon)

// WithLogger sets a custom logger object for the daemon.
func WithLogger(logger zerolog.Logger) DaemonOption {
	return func(d *Daemon) {
		d.log = logger
	}
}

// WithConfigPath sets a custom path to the daemon config.toml, overriding the
// default path in the config directory.
func WithConfigPath(path string) DaemonOption {
	return func(d *Daemon) {
		d.configPath = path
	}
}

// WithAuthKey sets the VPN auth key used to join the network non-interactively.
func WithAuthKey(authKey string) DaemonOption {
	return func(d *Daemon) {
		d.authKey = authKey
	}
}
