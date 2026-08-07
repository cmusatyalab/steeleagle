package tailscale

import (
	"context"
	"fmt"
	"net"

	"tailscale.com/ipn"
	"tailscale.com/ipn/store/mem"
	"tailscale.com/tsnet"
)

type Server struct {
	server *tsnet.Server
}

// NewServer starts a tsnet node under the given hostname. If authKey is
// non-empty it's used to join the tailnet non-interactively. Otherwise, tsnet
// falls back to its interactive login flow. tags, if non-empty, are advertised
// to control so the node comes up tagged. If ephemeral is true, the node keeps
// no state on disk, every call to NewServer re-registers from scratch.
func NewServer(hostname, authKey string, ephemeral bool, tags ...string) (*Server, error) {
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

	if len(tags) > 0 {
		lc, err := server.LocalClient()
		if err != nil {
			server.Close()
			return nil, fmt.Errorf("getting local client to advertise tags: %w", err)
		}
		_, err = lc.EditPrefs(context.Background(), &ipn.MaskedPrefs{
			AdvertiseTagsSet: true,
			Prefs:            ipn.Prefs{AdvertiseTags: tags},
		})
		if err != nil {
			server.Close()
			return nil, fmt.Errorf("advertising tags %v: %w", tags, err)
		}
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
