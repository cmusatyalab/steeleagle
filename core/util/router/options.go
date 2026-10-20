package router

import "github.com/rs/zerolog"

type RouterOption func(*Router)

// WithLogger sets a custom logger object for the router.
func WithLogger(logger zerolog.Logger) RouterOption {
	return func(r *Router) {
		r.log = logger
	}
}
