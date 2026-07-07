package vehicle

import (
	"github.com/cmusatyalab/steeleagle/core/util"
)

type PolicyConfig struct {
	Law ControlLaw
}

type PluginConfig struct {
	Driver  util.Plugin
	Mission util.Plugin
	Plugins []util.Plugin
}

type VideoStreamConfig struct {
	Codec      string
	Resolution VideoResolution
}
