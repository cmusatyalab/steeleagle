package vehicle

import (
	"net"
)

type PolicyConfig struct {
	// Control laws to use for RPC authorization policy
	Law ControlLaw
}

type ConnectionConfig struct {
	// WAN listener
	Listener net.Listener
	// IP access rights
	AllowedIPs []string
}
