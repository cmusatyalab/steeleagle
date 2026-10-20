package main

import (
	"net"
	"plugin"
	"sync/atomic"

	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc"
)

type pluginInfo struct {
	obj  plugin.Plugin    // plugin object
	ln   net.Listener     // listener for plugin
	conn *grpc.ClientConn // client connection to plugin
}

type missionInfo struct {
}

type Vehicle struct {
	Name     string               // vehicle name
	Dir      string               // path to vehicle runtime directory (absolute)
	Config   *config.PluginConfig // driver plugin config
	running  atomic.Bool          // whether of not the vehicle is currently running
	daemonLn net.Listener         // daemon listener
	driver   pluginInfo           // driver plugin reference
	mission  pluginInfo           // mission plugin reference
	services *grpc.Server
	err      error
	shutdown chan struct{}
}
