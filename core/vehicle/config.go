package vehicle

import (
	"net"

	"github.com/cmusatyalab/steeleagle/core/util"
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

type PluginConfig struct {
	driver  util.Plugin
	mission util.Plugin
	plugins []util.Plugin
}
