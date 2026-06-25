package vehicle

type VehicleOption func(*Vehicle)

func WithName(name string) VehicleOption {
	return func(k *Vehicle) {
		k.name = name
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
