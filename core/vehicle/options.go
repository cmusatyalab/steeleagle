package vehicle

import "net"

type VehicleOption func(*Vehicle)

func WithName(name string) VehicleOption {
	return func(k *Vehicle) {
		k.name = name
	}
}

func WithPath(path string) VehicleOption {
	return func(k *Vehicle) {
		k.path = path
	}
}

func WithServicePath(path string) VehicleOption {
	return func(k *Vehicle) {
		k.spath = path
	}
}

func WithTest() VehicleOption {
	return func(k *Vehicle) {
		k.test = true
	}
}

func WithPolicyConfig(policyCfg PolicyConfig) VehicleOption {
	return func(k *Vehicle) {
		k.policyCfg = policyCfg
	}
}

func WithNetListeners(listeners []net.Listener) VehicleOption {
	return func(k *Vehicle) {
		k.connections.externGRPC = listeners
	}
}

func WithBackend(backend string) VehicleOption {
	return func(k *Vehicle) {
		k.backend = backend
	}
}
