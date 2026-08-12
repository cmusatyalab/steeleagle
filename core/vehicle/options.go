package vehicle

import (
	"net"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
)

type VehicleOption func(*Vehicle)

func WithName(name string) VehicleOption {
	return func(v *Vehicle) {
		v.Name = name
	}
}

func WithPolicyConfig(policyCfg PolicyConfig) VehicleOption {
	return func(v *Vehicle) {
		v.policyCfg = policyCfg
	}
}

func WithVideoStreamConfig(videoCfg VideoStreamConfig) VehicleOption {
	return func(v *Vehicle) {
		v.videoCfg = videoCfg
	}
}

func WithGabrielConfig(gabrielCfg GabrielConfig) VehicleOption {
	return func(v *Vehicle) {
		v.gabrielCfg = gabrielCfg
	}
}

// WithDialer sets the Dialer outbound connections (e.g. to Gabriel) are
// sourced from. Leave unset to use gRPC's default dialer.
func WithDialer(dialer Dialer) VehicleOption {
	return func(v *Vehicle) {
		v.dialer = dialer
	}
}

func WithServerListener(ln net.Listener, acl *util.ACL) VehicleOption {
	return func(v *Vehicle) {
		codedLn := util.NewCodedListener(ln, util.ServerCode, acl)
		v.listeners[ServerListenerName] = codedLn
	}
}

func WithLogger(logger zerolog.Logger) VehicleOption {
	return func(v *Vehicle) {
		v.log = logger
	}
}
