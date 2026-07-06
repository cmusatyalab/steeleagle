package vehicle

import (
    "net"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type VehicleOption func(*Vehicle)

func WithName(name string) VehicleOption {
    return func(v *Vehicle) {
        v.name = name
    }
}

func WithPolicyConfig(policyCfg PolicyConfig) VehicleOption {
	return func(v *Vehicle) {
		v.policyCfg = policyCfg
	}
}

func WithDriverConn(conn *grpc.ClientConn) VehicleOption {
	return func(v *Vehicle) {
		v.driver = conn
	}
}

func WithMissionConn(conn *grpc.ClientConn) VehicleOption {
    return func(v *Vehicle) {
        v.mission = conn
    }
}

func WithMissionListener(ln net.Listener) VehicleOption {
    return func(v *Vehicle) {
        v.listeners[MissionListenerName] = ln
    }
}

func WithServerListener(ln net.Listener) VehicleOption {
    return func(v *Vehicle) {
        v.listeners[ServerListenerName] = ln
    }
}

func WithLogger(logger zerolog.Logger) VehicleOption {
	return func(v *Vehicle) {
		v.log = logger
	}
}
