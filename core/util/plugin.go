package util

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"

	"github.com/containers/podman/pkg/bindings/images"
	"github.com/containers/podman/v5/pkg/bindings"
	"github.com/containers/podman/v5/pkg/bindings/containers"
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
	Name() string
	Runtime() PluginRuntime
	Start(context.Context, map[string]string) error
	Stop() error
	IsRunning() bool
	Path() string
}

type BasePlugin struct {
	name     string
	path     string
	runtime  PluginRuntime
	sockFile *os.File
	start    int64 // plugin start time
	running  bool
}

type ProcessPlugin struct {
	BasePlugin
	pid int
	cmd *exec.Cmd
}

type ContainerPlugin struct {
	BasePlugin
	cid      string
	imageTag string
	connCtx  context.Context
	cmd      *exec.Cmd
}

type PluginOption func(*BasePlugin)

func CreateProcessPlugin(name, path string) (*ProcessPlugin, error) {

	info, err := os.Stat(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, err
		}
		return nil, err
	}

	if info.IsDir() {
		// find run hook
	}

	p := &ProcessPlugin{
		BasePlugin: BasePlugin{
			name:    name,
			path:    path,
			runtime: Process,
		},
	}
	if info.Mode()&0o111 != 0 {
		p.cmd = exec.Command(path)
	}

	return p, nil
}

func CreateContainerPlugin(ctx context.Context, name, path, imageTag string) (*ContainerPlugin, error) {
	// Get Podman socket location
	sock_dir := os.Getenv("XDG_RUNTIME_DIR")
	socket := "unix:" + sock_dir + "/podman/podman.sock"

	// Connect to Podman socket
	connCtx, err := bindings.NewConnection(ctx, socket)
	if err != nil {
		return nil, err
	}

	exists, err := images.Exists(connCtx, imageTag, nil)
	if err != nil {
		return nil, err
	}
	if !exists {
		return nil, fmt.Errorf("Image %q not found", imageTag)
	}

	p := &ContainerPlugin{
		BasePlugin: BasePlugin{
			name:    name,
			path:    path,
			runtime: Container,
		},
		connCtx:  connCtx,
		imageTag: imageTag,
	}
	return p, nil
}

func (p ProcessPlugin) Start(ctx context.Context) error {
	// Start the process
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.Name).Msg("could not run process for plugin")
		return err
	}

	file := os.NewFile(uintptr(fds[1]), "socket")
	p.cmd.ExtraFiles = []*os.File{file}
	err = p.cmd.Run()
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Msg("could not run process for plugin")
		return err
	}
	syscall.Close(fds[1])

	return nil
}

func (p *ProcessPlugin) Stop() {

}

func (p *ContainerPlugin) Start(ctx context.Context) error {
	// write container id to a tmp file
	cidFile, _ := os.CreateTemp("", "cid-*")
	cidFile.Close()
	defer os.Remove(cidFile.Name())

	// create a socket pair to communicate with the plugin
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		return err
	}
	p.sockFile = os.NewFile(uintptr(fds[0]), fmt.Sprintf("kernel-%s", p.name))
	pluginFile := os.NewFile(uintptr(fds[1]), fmt.Sprintf("plugin-%s", p.name))

	// run the container
	cmd := exec.CommandContext(ctx, "podman", "run", "--rm",
		"--cidfile", cidFile.Name(),
		"--preserve-fd", "3",
		p.imageTag)
	cmd.ExtraFiles = []*os.File{pluginFile}
	pluginFile.Close()
	if err := cmd.Run(); err != nil {
		return err
	}

	p.start = time.Now().UnixMilli()

	// get container id
	data, _ := os.ReadFile(cidFile.Name())
	p.cid = strings.TrimSpace(string(data))
	p.waitForRunning()
	return nil
}

func (p *ContainerPlugin) waitForRunning() error {
	for {
		running, err := p.isRunning()
		if err != nil {
			return err
		}
		if running {
			return nil
		}
		time.Sleep(50 * time.Millisecond)
	}
}

func (p *ContainerPlugin) isRunning() (bool, error) {
	data, err := containers.Inspect(p.connCtx, p.cid, nil)
	if err != nil {
		return false, err
	}
	return data.State.Running, nil
}

func (p *ContainerPlugin) Stop() err {
	if err := containers.Stop(p.connCtx, p.cid, nil); err != nil {
		return err
	}
	return p.c
}

func (p *BasePlugin) Name() string {
	return p.name
}

func (p *BasePlugin) Path() string {
	return p.path
}

func (p *BasePlugin) Runtime() PluginRuntime {
	return p.runtime
}

func (p *BasePlugin) IsRunning() bool {
	return p.running
}

var _ Plugin = (*ProcessPlugin)(nil)
var _ Plugin = (*ContainerPlugin)(nil)
