//go:build !notailscale

package network

import (
	"context"
	"fmt"
	"net"
	"net/netip"
	"strings"

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
// is non-empty it's used to join the tailnet non-interactively. If the
// control server rejects the login, the error wraps ErrLogin.
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
		// Up fails with the backend's error message, which it only has once
		// the control server refuses the login (a network that can't be
		// reached leaves Up waiting instead)
		if strings.HasPrefix(err.Error(), "tsnet.Up: backend: ") {
			return nil, fmt.Errorf("%w: %v", ErrLogin, err)
		}
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

// Resolve returns the tailnet IP addresses of host, which may be a literal IP,
// a peer hostname, or a peer's MagicDNS name. Names are only resolved against
// tailnet peers, never through outside DNS.
func (i *Server) Resolve(ctx context.Context, host string) ([]netip.Addr, error) {
	if addr, err := netip.ParseAddr(host); err == nil {
		return []netip.Addr{addr}, nil
	}
	client, err := i.server.LocalClient()
	if err != nil {
		return nil, err
	}
	status, err := client.Status(ctx)
	if err != nil {
		return nil, err
	}
	host = strings.TrimSuffix(host, ".")
	for _, peer := range status.Peer {
		dnsName := strings.TrimSuffix(peer.DNSName, ".")
		shortName, _, _ := strings.Cut(dnsName, ".")
		if strings.EqualFold(host, dnsName) || strings.EqualFold(host, shortName) ||
			strings.EqualFold(host, peer.HostName) {
			if len(peer.TailscaleIPs) == 0 {
				return nil, fmt.Errorf("tailnet peer %q has no addresses", host)
			}
			return peer.TailscaleIPs, nil
		}
	}
	return nil, fmt.Errorf("no tailnet peer found for %q", host)
}

// LocalAddr returns this node's tailnet IP address, preferring IPv4 unless
// remote is an IPv6 address. Every peer reaches this node at the same address.
func (i *Server) LocalAddr(ctx context.Context, remote netip.Addr) (netip.Addr, error) {
	ip4, ip6 := i.server.TailscaleIPs()
	if (remote.Is6() || !ip4.IsValid()) && ip6.IsValid() {
		return ip6, nil
	}
	if ip4.IsValid() {
		return ip4, nil
	}
	return netip.Addr{}, fmt.Errorf("tailscale node has no addresses")
}

func (i *Server) Close() {
	i.server.Close()
}
