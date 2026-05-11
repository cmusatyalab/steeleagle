package plugin

import (
	"context"
	"os/exec"
	"path/filepath"

	"github.com/rs/zerolog/log"
)

type PluginRuntime int

const (
	Process PluginRuntime = iota
	Container
	Sandbox
)

var pluginRuntimeName = map[PluginRuntime]string{
	Process:   "process",
	Container: "container",
	Sandbox:   "sandbox",
}

func (pr PluginRuntime) String() string {
	return pluginRuntimeName[pr]
}

type Plugin interface {
	Start() error
	Stop()
	IsRunning() bool
	Path() string
}

type BasePlugin struct {
	name string
	path string
	// Runtime attributes
	spath string  // socket path, if running as a server connection type
	start float64 // plugin start time
}

type ProcessPlugin struct {
	BasePlugin
	pid  int
	proc *exec.Cmd
}

type ContainerPlugin struct {
	BasePlugin
	cid string
}

type PluginOption func(*BasePlugin)

func CreateProcessPlugin(name, path, spath string) (*ProcessPlugin, error) {
	return nil, nil
}

func CreateContainerPlugin(name, path, spath, image_tag string) (*ContainerPlugin, error) {
	return nil, nil
}

//func CreatePlugin(options ...PluginOption) (*Plugin, error) {
//	// Set the path to the plugin directory
//	if i.path == "" {
//		i.path = filepath.Join(xdg.DataDir, ApplicationName, i.Name)
//	}
//}

func (p ProcessPlugin) Start(ctx context.Context, envVarsmap map[string]string) error {
	// Start the process
	cmd := exec.Command(filepath.Join(p.path, PluginRunScript))
	err := cmd.Run()
	if err != nil {
		log.Error().Err(err).Str("plugin", i.Name).Msg("could not run process for plugin")
		return err
	}

	//switch i.Runtime {
	//case PluginRuntime.Process:
	//	// Start the process
	//	cmd := exec.Command(filepath.Join(i.Path, PluginRunScript))
	//	err := cmd.Run()
	//	if err != nil {
	//		log.Error().Err(err).Str("plugin", i.Name).Msg("could not run process for plugin")
	//		return err
	//	}
	//case PluginRuntime.Container:
	//	// Check if image exists locally
	//	exists, err := images.Exists(ctx, i.name, nil)
	//	if err != nil {
	//		log.Error().Err(err).Str("plugin", i.name).Msg("could not check for container images")
	//		return err
	//	}
	//	if !exists {
	//		log.Warn().Str("plugin", i.name).Msg("could not find container locally, attempting to pull")
	//	}

	//	// Proceed to create + start as normal
	//	s := specgen.NewSpecGenerator(i.name, false)

	//	// Create mounts for the right files

	//	resp, err := containers.CreateWithSpec(ctx, s, nil)
	//	if err != nil {
	//		log.Error().Err(err).Str("plugin", i.name).Msg("could not create container, aborting")
	//		return err
	//	}
	//	// Set the container ID
	//	i.cid = resp.ID

	//	// TODO: look up PID from CID
	//case PluginRuntime.Sandbox:
	//}

}

// Status methods
func (i *Plugin) Name() string {
	return i.name
}

func (i *Plugin) Path() string {
	return i.path
}

func (i *Plugin) Runtime() PluginRuntime {
	return i.runtime
}

func (i *Plugin) ConnType() PluginConnType {
	return i.connType
}

func (i *Plugin) PID() int {
	return i.pid
}

func (i *Plugin) IsRunning() bool {
	return i.pid != 0
}
