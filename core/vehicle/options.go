package vehicle

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
