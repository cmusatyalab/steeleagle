package core

import "net"

type VehicleOption func(*Vehicle)

func WithName(name string) func(*Vehicle) {
    return func(k *Vehicle) {
        k.Name = name
    }
}

func WithTest(test bool) func(*Vehicle) {
    return func(k *Vehicle) {
        k.test = test
    }
}

func WithPolicyFile(filename string) func(*Vehicle) {
    return func(k *Vehicle) {
        k.lawFile = filename
    }
}

func WithExternalLinks(links []net.Listener) func(*Vehicle) {
    return func(k *Vehicle) {
        k.connections.externConns = links
    }
}
