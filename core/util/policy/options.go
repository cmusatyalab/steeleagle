package policy

import "github.com/rs/zerolog"

type PolicyOption func(*Policy)

// WithLogger sets a custom logger object for the policy.
func WithLogger(logger zerolog.Logger) PolicyOption {
	return func(p *Policy) {
		p.log = logger
	}
}

// WithRego sets a custom Rego OPA config for the policy, overriding DefaultRego.
func WithRego(rego string) PolicyOption {
	return func(p *Policy) {
		p.rego = rego
	}
}
