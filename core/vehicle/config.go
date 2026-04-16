package vehicle

import "net"

type PolicyConfig struct {
    // Control laws to use for RPC authorization policy
    Law         ControlLaw
}

// Vehicle Options
type VehicleOption func(*Vehicle)

func WithName(name string) VehicleOption {
    return func(k *Vehicle) {
        k.name = name
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

func WithExternalLinks(links []net.Listener) VehicleOption {
    return func(k *Vehicle) {
        k.connections.externGRPC = links
    }
}

// Backend Options
type BackendOption func(*Backend)

func WithConnectedVehicles(vehicles []ConnectedVehicle) BackendOption {
    return func(k *Backend) {
        for index, vehicle := range(vehicles) {
            k.vehicles[vehicle.Name] = vehicles[index]
        }
    }
}

func WithoutDataplane() BackendOption {
    return func(k *Backend) {
        k.useDataplane = false
    }
}
