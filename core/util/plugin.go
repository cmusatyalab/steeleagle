package util

import (
	"net"
    "context"
    "fmt"

	"google.golang.org/grpc"
)

type Plugin interface {
	Name() string
	Runtime() PluginRuntime
	Spawn(context.Context) (net.Listener, *grpc.ClientConn, error)
	Stop() error
	IsRunning() bool
	Target() string
}

type BasePlugin struct {
	name    string
	target  string
	runtime PluginRuntime
	start   int64 // plugin start time
	running bool
	code    AuthCode
}

func (p *BasePlugin) Name() string {
	return p.name
}

func (p *BasePlugin) Runtime() PluginRuntime {
	return p.runtime
}

func (p *BasePlugin) Target() string {
	return p.target
}

func (p *BasePlugin) IsRunning() bool {
	return p.running
}
