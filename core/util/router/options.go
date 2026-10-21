package router

import "github.com/rs/zerolog"

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

// WithLogger sets a custom logger object for the router.
func WithLogger(logger zerolog.Logger) RouterOption {
	return func(r *Router) {
		r.log = logger
	}
}
