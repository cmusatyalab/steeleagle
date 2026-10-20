package policy

import "github.com/rs/zerolog"

type PolicyOption func(*Policy)

// WithLogger sets a custom logger object for the policy.
func WithLogger(logger zerolog.Logger) PolicyOption {
	return func(p *Policy) {
		p.log = logger
	}
}
