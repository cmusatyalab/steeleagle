package vehicle

import (
	"net"

	"github.com/cmusatyalab/steeleagle/core/util"
)

type PolicyConfig struct {
	Law ControlLaw
}

type PluginConfig struct {
	Driver  *util.Plugin
	Mission *util.Plugin
	Plugins []*util.Plugin
}
