package vehicle

import (
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type VehicleOption func(*Vehicle)

func WithId(id string) VehicleOption {
	return func(v *Vehicle) {
		v.id = id
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

func WithLogger(logger zerolog.Logger) VehicleOption {
	return func(v *Vehicle) {
		v.log = logger
	}
}
