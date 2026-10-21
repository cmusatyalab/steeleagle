//go:build notailscale

package network

import (
	"context"
	"fmt"
	"net"
	"net/netip"
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

// Resolve returns the IP addresses of host, which may be a literal IP or a
// name resolved through the host's DNS resolver.
func (i *Server) Resolve(ctx context.Context, host string) ([]netip.Addr, error) {
	if addr, err := netip.ParseAddr(host); err == nil {
		return []netip.Addr{addr}, nil
	}
	addrs, err := net.DefaultResolver.LookupNetIP(ctx, "ip", host)
	if err != nil {
		return nil, err
	}
	for j, addr := range addrs {
		addrs[j] = addr.Unmap()
	}
	return addrs, nil
}

// LocalAddr returns the host IP address that traffic to remote is sourced
// from. No packets are sent; connecting a UDP socket only picks the route.
func (i *Server) LocalAddr(ctx context.Context, remote netip.Addr) (netip.Addr, error) {
	conn, err := i.dialer.DialContext(ctx, "udp", netip.AddrPortFrom(remote, 9).String())
	if err != nil {
		return netip.Addr{}, err
	}
	defer conn.Close()
	return conn.LocalAddr().(*net.UDPAddr).AddrPort().Addr().Unmap(), nil
}

// Close is a no-op: listeners and connections handed out are owned by the
// caller, and the host network has nothing to tear down.
func (i *Server) Close() {}
