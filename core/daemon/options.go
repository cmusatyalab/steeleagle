package daemon

import "github.com/rs/zerolog"

type DaemonOption func(*Daemon)

// WithLogger sets a custom logger object for the daemon.
func WithLogger(logger zerolog.Logger) DaemonOption {
	return func(d *Daemon) {
		d.log = logger
	}
}

// WithAuthKey sets the VPN auth key used to join the network non-interactively.
func WithAuthKey(authKey string) DaemonOption {
	return func(d *Daemon) {
		d.netAuth = authKey
	}
}
