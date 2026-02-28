package core

import "net"

type policyConfig struct {
    // Path to custom file containing law specification, or left blank
    // to use default included laws
    filename    string
}

type LogConfig struct {
    // Name for the logger
    Name        string
    // Log level for application logs
    Level       string
    // Channel to write output of logs
    Channel     chan<- LogMessage
}

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

func WithLogLevel(level string) func(*Vehicle) {
    return func(k *Vehicle) {
        k.logCfg.Level = level
    }
}

func WithPolicyFile(filename string) func(*Vehicle) {
    return func(k *Vehicle) {
        k.policyCfg.filename = filename
    }
}

func WithExternalLinks(links []net.Listener) func(*Vehicle) {
    return func(k *Vehicle) {
        k.connections.externGRPC = links
    }
}
