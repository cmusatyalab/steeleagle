//go:build notailscale

package network

import (
	"context"
	"fmt"
	"net"
)

// Tailscale reports whether this build routes through tailscale (true) or the
// host network (false, under the notailscale build tag).
const Tailscale = false

// Server is a handle on the host's own network stack, standing in for a tsnet
// node in builds without tailscale.
type Server struct {
	dialer net.Dialer
}

// NewServer returns a Server backed by the host network. It mirrors the
// tailscale build's signature so callers compile unchanged, but hostname
// and authKey have no effect.
func NewServer(ctx context.Context, hostname, authKey string) (*Server, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	return new(Server), nil
}

// Listen listens on port on every host interface.
func (i *Server) Listen(protocol string, port int) (net.Listener, error) {
	return net.Listen(protocol, fmt.Sprintf(":%d", port))
}

// Dial opens an outbound connection from the host network.
func (i *Server) Dial(ctx context.Context, network, addr string) (net.Conn, error) {
	return i.dialer.DialContext(ctx, network, addr)
}

// Close is a no-op: listeners and connections handed out are owned by the
// caller, and the host network has nothing to tear down.
func (i *Server) Close() {}
