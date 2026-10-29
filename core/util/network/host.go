package network

import (
	"context"
	"fmt"
	"net"
	"net/netip"
	"strconv"
	"time"
)

// bindPoll is how often NewServer checks whether the host has the bind
// address yet.
const bindPoll = time.Second

// Server is a handle on the host's own network stack. A VPN, like tailscale,
// runs on the host and is reached through its interface.
type Server struct {
	dialer net.Dialer
	bind   netip.Addr // address listeners bind to, invalid for every interface
}

// NewServer returns a Server backed by the host network. If bind is
// non-empty, it must be an IP address, which NewServer waits for the host to
// have, or ctx to be done, whichever comes first; the server then listens and
// dials from that address only. Otherwise it listens on every interface.
func NewServer(ctx context.Context, bind string) (*Server, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	server := new(Server)
	if bind == "" {
		return server, nil
	}
	addr, err := netip.ParseAddr(bind)
	if err != nil {
		return nil, fmt.Errorf("invalid bind address: %w", err)
	}
	addr = addr.Unmap()
	ok, err := hasAddr(addr)
	if ok {
		server.bind = addr
		server.dialer.LocalAddr = &net.TCPAddr{IP: addr.AsSlice()}
		return server, nil
	}
	return nil, fmt.Errorf("no interface has address %s", addr)
}

// hasAddr reports whether an interface of the host has the address addr.
func hasAddr(addr netip.Addr) (bool, error) {
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return false, err
	}
	for _, a := range addrs {
		prefix, err := netip.ParsePrefix(a.String())
		if err == nil && prefix.Addr().Unmap() == addr {
			return true, nil
		}
	}
	return false, nil
}

// Listen listens on port on the bind address, or every host interface if
// there is none.
func (i *Server) Listen(protocol string, port int) (net.Listener, error) {
	return net.Listen(protocol, net.JoinHostPort(i.BindHost(), strconv.Itoa(port)))
}

// Dial opens an outbound TCP connection from the bind address, or the host
// network if there is none.
func (i *Server) Dial(ctx context.Context, network, addr string) (net.Conn, error) {
	return i.dialer.DialContext(ctx, network, addr)
}

// BindHost returns the address that listeners bind to, or "" for every
// interface.
func (i *Server) BindHost() string {
	if !i.bind.IsValid() {
		return ""
	}
	return i.bind.String()
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

// LocalAddr returns the bind address if there is one, else the host IP
// address that traffic to remote is sourced from. No packets are sent;
// connecting a UDP socket only picks the route.
func (i *Server) LocalAddr(ctx context.Context, remote netip.Addr) (netip.Addr, error) {
	if i.bind.IsValid() {
		return i.bind, nil
	}
	var dialer net.Dialer
	conn, err := dialer.DialContext(ctx, "udp", netip.AddrPortFrom(remote, 9).String())
	if err != nil {
		return netip.Addr{}, err
	}
	defer conn.Close()
	return conn.LocalAddr().(*net.UDPAddr).AddrPort().Addr().Unmap(), nil
}

// Close is a no-op: listeners and connections handed out are owned by the
// caller, and the host network has nothing to tear down.
func (i *Server) Close() {}
