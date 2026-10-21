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

// WithRemoteCompute sets the address and cert of the remote compute service
// provided by the orchestrator.
func WithRemoteCompute(address, cert string) VehicleOption {
	return func(v *Vehicle) {
		v.remoteAddr = address
		v.remoteCert = cert
	}
}
