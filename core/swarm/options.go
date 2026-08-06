package swarm

import (
	"time"

	"github.com/rs/zerolog"
)

type Option func(*Server)

// WithLogger overrides the Server's default logger.
func WithLogger(logger zerolog.Logger) Option {
	return func(s *Server) {
		s.log = logger
	}
}

// WithCallTimeout overrides the bound placed on each per-vehicle proxied call,
// in place of defaultCallTimeout.
func WithCallTimeout(timeout time.Duration) Option {
	return func(s *Server) {
		s.timeout = timeout
	}
}
