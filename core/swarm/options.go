package swarm

import (
	"context"
	"net"
	"time"

	"github.com/rs/zerolog"
)

type Option func(*SwarmServer)

// WithLogger overrides the SwarmServer's default logger.
func WithLogger(logger zerolog.Logger) Option {
	return func(s *SwarmServer) {
		s.log = logger
	}
}

// WithCallTimeout overrides the bound placed on each per-vehicle proxied call.
func WithCallTimeout(timeout time.Duration) Option {
	return func(s *SwarmServer) {
		s.timeout = timeout
	}
}

// WithDialer routes outbound vehicle connections through dialer instead of
// the default network stack -- e.g. a tsnet.Server.Dial so calls are sourced
// from the swarm controller's own tailnet identity and can actually reach
// tailnet-only vehicle addresses.
func WithDialer(dialer func(ctx context.Context, network, addr string) (net.Conn, error)) Option {
	return func(s *SwarmServer) {
		s.pool.dialer = dialer
	}
}
