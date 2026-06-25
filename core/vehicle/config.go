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

type Runnable struct {
	runtime util.PluginRuntime
	// image name and tag for a container, or file path for a binary
	target string
}

type PluginConfig struct {
	driver  Runnable
	mission Runnable
	admin   Runnable
	plugins []Runnable
}
