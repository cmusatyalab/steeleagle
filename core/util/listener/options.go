package listener

import "github.com/rs/zerolog"

type ListenerOption func(*codedListener)

// WithLogger sets a custom logger object for the listener.
func WithLogger(logger zerolog.Logger) ListenerOption {
	return func(l *codedListener) {
		l.log = logger
	}
}
