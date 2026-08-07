package tailscale

import (
	"context"
	"fmt"
	"net"

	"tailscale.com/ipn/store/mem"
	"tailscale.com/tsnet"
)

type Server struct {
	server *tsnet.Server
}

// NewServer starts a tsnet node under the given hostname. If authKey is
// non-empty it's used to join the tailnet non-interactively. Otherwise, tsnet
// falls back to its interactive login flow. Tags, if any, should be baked
// into authKey itself (created with those tags in the admin console) so the
// node registers already-tagged in one step, rather than being set here via
// a post-boot EditPrefs call. If ephemeral is true, the node keeps no state
// on disk, every call to NewServer re-registers from scratch.
func NewServer(hostname, authKey string, ephemeral bool) (*Server, error) {
	server := new(tsnet.Server)
	server.Hostname = hostname
	server.AuthKey = authKey
	server.Ephemeral = ephemeral
	if ephemeral {
		server.Store = new(mem.Store)
	}

	// Start the Tailscale server
	if err := server.Start(); err != nil {
		return nil, err
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
