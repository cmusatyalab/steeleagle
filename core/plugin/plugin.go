package plugin

import (
    "os/exec"
    "context"
    "path/filepath"

    "github.com/adrg/xdg"
    "github.com/rs/zerolog/log"
)

type PluginRuntime int

const (
    Process   PluginRuntime = iota
    Container PluginRuntime
    Sandbox   PluginRuntime
)

type Plugin struct {
    name      string
    path      string
    runtime   PluginRuntime
    // Runtime attributes
    pid       int
    cid       string // container ID, if running as a container
    spath     string // socket path, if running as a server connection type
    proc      *exec.Cmd // process object, if running as a process
    start     float64 // process start time, used to differentiate PIDs if they are recycled
    // Context related attributes
    ctx       context.Context
    cancel    context.CancelFunc
}

func CreatePlugin(parentCtx context.Context, options ...PluginOption) (*Plugin, error) {
    // Set the path to the plugin directory
    if i.path == "" {
        i.path = filepath.Join(xdg.DataDir, ApplicationName, i.Name)
    }
}

func (i *Plugin) Start(map[string]string envVars) error {
    switch i.Runtime {
        case PluginRuntime.Process:
            // Start the process
            cmd := exec.Command(filepath.Join(i.Path, PluginRunScript))
            err := cmd.Run()
            if err != nil {
                log.Error().Err(err).Str("plugin", i.Name).Msg("could not run process for plugin")
                return err
            }
        case PluginRuntime.Container:
            // Check if image exists locally
            exists, err := images.Exists(ctx, i.name, nil)
            if err != nil {
                log.Error().Err(err).Str("plugin", i.name).Msg("could not check for container images")
                return err
            }
            if !exists {
                log.Warn().Str("plugin", i.name).Msg("could not find container locally, attempting to pull")
            }
            
            // Proceed to create + start as normal
            s := specgen.NewSpecGenerator(i.name, false)

            // Create mounts for the right files
            
            resp, err := containers.CreateWithSpec(ctx, s, nil)
            if err != nil {
                log.Error().Err(err).Str("plugin", i.name).Msg("could not create container, aborting")
                return err
            }
            // Set the container ID
            i.cid = resp.ID

            // TODO: look up PID from CID
        case PluginRuntime.Sandbox:
    }

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
