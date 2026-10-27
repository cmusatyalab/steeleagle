package network

import (
	"context"
	"net"
	"net/netip"
)

// Network is a network a daemon can join, which is a tailnet in builds with
// tailscale, and the host network otherwise. Server implements it in either
// build; tests can stand in their own.
type Network interface {
	// Listen listens on port on this node.
	Listen(protocol string, port int) (net.Listener, error)
	// Dial opens an outbound connection from this node.
	Dial(ctx context.Context, network, addr string) (net.Conn, error)
	// Resolve returns the IP addresses of host.
	Resolve(ctx context.Context, host string) ([]netip.Addr, error)
	// LocalAddr returns this node's address, as seen by remote.
	LocalAddr(ctx context.Context, remote netip.Addr) (netip.Addr, error)
	// Close leaves the network.
	Close()
}

var _ Network = (*Server)(nil)
