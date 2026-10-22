package vehicle

import "github.com/rs/zerolog"

type VehicleOption func(*Vehicle)

// WithLogger sets a custom logger object for the vehicle.
func WithLogger(logger zerolog.Logger) VehicleOption {
	return func(v *Vehicle) {
		v.log = logger
	}
}

// WithName sets a custom name for the vehicle, overriding the generated UUID.
func WithName(name string) VehicleOption {
	return func(v *Vehicle) {
		v.Name = name
	}
}

// WithLaw sets a custom control law (TOML bytes) for the vehicle.
func WithLaw(lawToml []byte) VehicleOption {
	return func(v *Vehicle) {
		v.lawToml = lawToml
	}
}

// WithLcs sets the name of the local compute service, the Uriel server on this
// machine that the vehicle's dataflows reach local engines through.
func WithLcs(server string) VehicleOption {
	return func(v *Vehicle) {
		v.lcsName = server
	}
}

// WithAvailableEngines sets the engines that the vehicle's dataflows can use,
// by qualified name. A dataflow with any other engine is rejected, and the
// results of each engine are stored as its result type.
func WithAvailableEngines(engines map[string]Engine) VehicleOption {
	return func(v *Vehicle) {
		v.engines = engines
	}
}

// WithRcs sets the address and DER encoded cert of the remote compute service
// provided by the orchestrator.
func WithRcs(address string, cert []byte) VehicleOption {
	return func(v *Vehicle) {
		v.rcsAddr = address
		v.rcsCert = cert
	}
}
