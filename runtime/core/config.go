package core

import "log/slog"

type VehicleOption func(*Vehicle)

func WithName(name string) func(*Vehicle) {
    return func(k *Vehicle) {
        k.Name = name
    }
}

func WithPort(port int) func(*Vehicle) {
    return func(k *Vehicle) {
        k.connections.port = port
    }
}

func WithVPN(vpn bool) func(*Vehicle) {
    return func(k *Vehicle) {
        k.connections.useVPN = true
    }
}

func WithTest(test bool) func(*Vehicle) {
    return func(k *Vehicle) {
        k.test = test
        k.logLevel.Set(slog.LevelDebug)
    }
}
