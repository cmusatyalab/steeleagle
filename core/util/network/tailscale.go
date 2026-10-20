//go:build !notailscale

package network

import (
	"context"
	"fmt"
	"net"

	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"tailscale.com/tsnet"
)

// Tailscale reports whether this build routes through tailscale (true) or the
// host network (false, under the notailscale build tag).
const Tailscale = true

type Server struct {
	server *tsnet.Server
}

// NewServer starts a tsnet node under the given hostname and blocks until it
// joins the tailnet or ctx is done, whichever comes first. If authKey
// is non-empty it's used to join the tailnet non-interactively.
func NewServer(ctx context.Context, hostname, authKey string) (*Server, error) {
	server := new(tsnet.Server)
	server.Hostname = hostname
	server.AuthKey = authKey
	server.Ephemeral = false

	var err error
	server.Dir, err = util.GetVpnDir()
	if err != nil {
		return nil, err
	}
	// Start the Tailscale server
	if err = server.Start(); err != nil {
		return nil, err
	}
	if _, err = server.Up(ctx); err != nil {
		server.Close()
		return nil, fmt.Errorf("waiting for tailscale node %q to come up: %w", hostname, err)
	}

	return &Server{
		server: server,
	}, nil
}

func (i *Server) Listen(protocol string, port int) (net.Listener, error) {
	conn, err := i.server.Listen(protocol, fmt.Sprintf(":%d", port))
	if err != nil {
		return nil, err
	}

	return conn, nil
}

// Dial opens an outbound connection sourced from this node's own tailnet
// identity, so peers see this node's address, not the host's.
func (i *Server) Dial(ctx context.Context, network, addr string) (net.Conn, error) {
	return i.server.Dial(ctx, network, addr)
}

func (i *Server) Close() {
	i.server.Close()
}
