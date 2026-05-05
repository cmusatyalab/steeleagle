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

// NewFilterListener creates a FilterListener from any net.Listener.
// A FilterListener filters incoming WAN gRPC connections based on the
// current vehicle policy.
func (i *policyState) NewFilterListener(listener net.Listener) (*FilterListener, error) {
	return &FilterListener{listener: listener, allowed: allowed}, nil
}

func (i *FilterListener) Accept() (net.Conn, error) {
	for {
		conn, err := i.listener.Accept()
		if err != nil {
			return nil, err
		}
		if i.isAllowed(conn.RemoteAddr()) {
			return conn, nil
		}
		conn.Close() // Drop the connection if the IP is not on the whitelist
	}
}

func (i *FilterListener) isAllowed(addr net.Addr) bool {
	host, _, err := net.SplitHostPort(addr.String())
	if err != nil {
		return false
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return false
	}

	for _, entry := range i.allowed {
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
