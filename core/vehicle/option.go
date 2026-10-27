package vehicle

import (
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/rs/zerolog"
)

type VehicleOption func(*Vehicle)

func WithName(name string) VehicleOption {
	return func(v *Vehicle) {}
}

// WithAuthCode sets the auth code of calls from the vehicle to the daemon.
func WithAuthCode(code listener.AuthCode) VehicleOption {
	return func(v *Vehicle) {
		v.auth = code
	}
}

func WithLogger(logger zerolog.Logger) VehicleOption {
	return func(v *Vehicle) {}
}

func WithMissionDir(dir string) VehicleOption {
	return func(v *Vehicle) {}
}

func WithLocalCompute(hostname string, engines EngineMap) VehicleOption {
	return func(v *Vehicle) {}
}

// WithLocalAndRemoteCompute gives the vehicle the local compute service, and
// the remote one of the orchestrator at addr (host:port), which it trusts by
// its DER cert.
func WithLocalAndRemoteCompute(
	hostname string,
	addr string,
	cert []byte,
	engines EngineMap,
) VehicleOption {
	return func(v *Vehicle) {}
}
