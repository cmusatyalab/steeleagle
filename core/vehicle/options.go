package vehicle

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

func WithSocketPath(path string) VehicleOption {
	return func(k *Vehicle) {
		k.socketPath = path
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

func WithConnectionConfig(connCfg ConnectionConfig) VehicleOption {
	return func(k *Vehicle) {
		k.connCfg = connCfg
	}
}

func WithBackend(backend string) VehicleOption {
	return func(k *Vehicle) {
		k.backend = backend
	}
}
