package vehicle

import (
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/rs/zerolog"
)

type VehicleOption func(*Vehicle)

// WithName sets the vehicle name, which names its producers, its Uriel client
// and its directories, and is the routing key of calls to it.
func WithName(name string) VehicleOption {
	return func(v *Vehicle) {
		v.Name = name
	}
}

// WithAuthCode sets the auth code of calls from the vehicle to the daemon.
func WithAuthCode(code listener.AuthCode) VehicleOption {
	return func(v *Vehicle) {
		v.auth = code
	}
}

// WithLogger sets a custom logger object for the vehicle.
func WithLogger(logger zerolog.Logger) VehicleOption {
	return func(v *Vehicle) {
		v.log = logger
	}
}

// WithMissionDir sets the directory missions are uploaded to, instead of the
// vehicle's own under the data directory.
func WithMissionDir(dir string) VehicleOption {
	return func(v *Vehicle) {
		v.MissionDir = dir
	}
}

// WithLocalCompute gives the vehicle the local compute service, named
// hostname, and the engines its dataflows can use.
func WithLocalCompute(hostname string, engines EngineMap) VehicleOption {
	return func(v *Vehicle) {
		v.compute.lcs = hostname
		v.engines = engines
	}
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
	return func(v *Vehicle) {
		v.compute.lcs, v.compute.rcs, v.compute.cert = hostname, addr, cert
		v.engines = engines
	}
}
