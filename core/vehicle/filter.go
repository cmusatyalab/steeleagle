package vehicle

import (
	"net"
	"strings"
)

// FilterListener wraps any net.Listener and rejects connections
// from non-whitelisted IPs before they reach gRPC.
type filterListener struct {
	listener net.Listener
	allowed  []string
}

// NewFilterListener creates a filterListener from any net.Listener.
// A filterListener filters incoming WAN gRPC connections based on the
// current vehicle policy.
func (s *policyState) NewFilterListener(listener net.Listener) (*filterListener, error) {
	// TODO: figure out how to populate 'allowed'
	return &filterListener{listener: listener}, nil
}

func (l *filterListener) Accept() (net.Conn, error) {
	for {
		conn, err := l.listener.Accept()
		if err != nil {
			return nil, err
		}
		if l.isAllowed(conn.RemoteAddr()) {
			return conn, nil
		}
		conn.Close() // Drop the connection if the IP is not on the whitelist
	}
}

func (l *filterListener) Close() error {
	return l.listener.Close()
}

func (l *filterListener) Addr() net.Addr {
	return l.listener.Addr()
}

func (l *filterListener) isAllowed(addr net.Addr) bool {
	host, _, err := net.SplitHostPort(addr.String())
	if err != nil {
		return false
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return false
	}

	for _, entry := range l.allowed {
		if strings.Contains(entry, "/") {
			// CIDR range check
			_, network, err := net.ParseCIDR(entry)
			if err == nil && network.Contains(ip) {
				return true
			}
		} else {
			// Plain IP check
			if net.ParseIP(entry).Equal(ip) {
				return true
			}
		}
	}
	return false
}

var _ net.Listener = (*filterListener)(nil)
