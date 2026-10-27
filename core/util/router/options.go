package router

import (
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type RouterOption func(*Router)

// WithHeaderFallback routes calls with a routing key the router doesn't know
// by service, instead of rejecting them. It is for a router at the end of a
// route, like a vehicle's, where the key that routed a call there names the
// router itself.
func WithHeaderFallback() RouterOption {
	return func(r *Router) {
		r.fallback = true
	}
}

// WithUpstream routes calls whose routing key names anything other than self
// to conn, the route out of a router at the end of a route, like a vehicle's.
// Calls with self as their key are routed as if they had none, so they never
// go back out.
func WithUpstream(self string, conn *grpc.ClientConn) RouterOption {
	return func(r *Router) {
		r.self, r.upstream = self, conn
	}
}

// WithLogger sets a custom logger object for the router.
func WithLogger(logger zerolog.Logger) RouterOption {
	return func(r *Router) {
		r.log = logger
	}
}
