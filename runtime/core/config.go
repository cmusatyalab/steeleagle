package core

import "net"

type PolicyConfig struct {
    // Control laws to use for RPC authorization policy
    Law         ControlLaw
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

func WithLogConfig(logCfg LogConfig) func(*Vehicle) {
    return func(k *Vehicle) {
        k.logCfg = logCfg
    }
}

func WithPolicyConfig(policyCfg PolicyConfig) func(*Vehicle) {
    return func(k *Vehicle) {
        k.policyCfg = policyCfg
    }
}

func WithExternalLinks(links []net.Listener) func(*Vehicle) {
    return func(k *Vehicle) {
        k.connections.externGRPC = links
    }
}
