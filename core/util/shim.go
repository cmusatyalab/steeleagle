package util

import (
	"context"
	"fmt"
	"net"

	"google.golang.org/grpc"
)

type ShimPlugin struct {
	*BasePlugin
}

// CreateShimPlugin creates a ShimPlugin that wraps over an already running plugin.
// This shifts the plugin lifetime management to an external source, and can be
// useful for integrating third-party architectures. The client and listen socket
// paths are the paths where the already-running plugin expects the sockets to be;
// they can optionally be left blank if they are not needed.
func CreateShimPlugin(clientSocketPath, listenSocketPath string, options ...PluginOption) (*ShimPlugin, error) {
	// We don't want any script validation since we aren't running a script
	options = append(options, WithoutCheck())
	internal, err := CreateBasePlugin(options...)
	if err != nil {
		return nil, err
	}

	// Construct the shim
	p := &ShimPlugin{
		BasePlugin: internal,
	}
	if clientSocketPath != "" {
		p.cSock = clientSocketPath
	} else {
		p.client = false // if no client socket path is provided, there is no server
	}
	if listenSocketPath != "" {
		p.lnSock = listenSocketPath
	} else {
		p.listen = false // if no listen socket path is provided, there is no client
	}

	return p, nil
}

// Start returns the client and listen endpoints.
func (p *ShimPlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Prevent against multiple Start() calls while running
	if !p.running.CompareAndSwap(false, true) {
		return nil, nil, fmt.Errorf("plugin already running")
	}
	p.ctx = ctx

	go func() {
		<-ctx.Done()
		p.running.Store(false)
	}()

	return p.createSocketEndpoints()
}

func (p *ShimPlugin) Wait() error {
	<-p.ctx.Done()
	return nil
}

var _ Plugin = (*ShimPlugin)(nil)
