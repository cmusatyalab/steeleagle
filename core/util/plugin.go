package util

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"

	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
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
	Start(context.Context) error
	Stop() error
	IsRunning() bool
	Target() string
	Conn() *grpc.ClientConn
}

type BasePlugin struct {
	name    string
	target  string
	runtime PluginRuntime
	conn    *grpc.ClientConn
	start   int64 // plugin start time
	running bool
	cmd     *exec.Cmd
}

type ProcessPlugin struct {
	BasePlugin
	pid int
}

type ContainerPlugin struct {
	BasePlugin
	cid string
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
			target:  path,
			runtime: Process,
		},
	}
	if info.Mode()&0o111 != 0 {
		p.cmd = exec.Command(path)
	}

	return p, nil
}

func CreateContainerPlugin(name, imageRef string) (*ContainerPlugin, error) {

	err := exec.Command("podman", "image", "exists", imageRef).Run()
	if err != nil {
		return nil, err
	}
	if exitErr, ok := err.(*exec.ExitError); ok {
		if exitErr.ExitCode() == 1 {
			return nil, fmt.Errorf("Container image not found")
		}
	}
	p := &ContainerPlugin{
		BasePlugin: BasePlugin{
			name:    name,
			runtime: Container,
			target:  imageRef,
		},
	}
	return p, nil
}

func (p ProcessPlugin) Start(ctx context.Context) error {
	// Start the process
	pluginFile, err := p.createSocketpair()
	if err != nil {
		return err
	}
	p.cmd.ExtraFiles = []*os.File{pluginFile}
	err = p.cmd.Run()
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Msg("could not run process for plugin")
		return err
	}
	p.postStart()
	return nil
}

func (p *ProcessPlugin) Stop() error {
	return nil
}

func (p *ContainerPlugin) Start(ctx context.Context) error {
	// write container id to a tmp file
	cidFile, _ := os.CreateTemp("", "cid-*")
	cidFile.Close()
	defer os.Remove(cidFile.Name())

	pluginFile, err := p.createSocketpair()
	if err != nil {
		return err
	}

	// run the container
	cmd := exec.CommandContext(ctx, "podman", "run", "--rm",
		"--cidfile", cidFile.Name(),
		"--preserve-fd", "3",
		p.target)
	cmd.ExtraFiles = []*os.File{pluginFile}
	if err := cmd.Run(); err != nil {
		return err
	}
	pluginFile.Close()

	// get container id
	data, _ := os.ReadFile(cidFile.Name())
	p.cid = strings.TrimSpace(string(data))
	p.waitForRunning()

	p.postStart()

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
	out, err := exec.Command("podman", "inspect",
		"--format", "{{.State.Running}}",
		p.cid,
	).Output()
	if err != nil {
		return false, err
	}
	return strings.TrimSpace(string(out)) == "true", nil
}

func (p *ContainerPlugin) Stop() error {
	if err := exec.Command("podman", "stop", p.cid).Run(); err != nil {
		return err
	}
	return p.cmd.Wait()
}

func (p *BasePlugin) createSocketpair() (*os.File, error) {
	// create a socket pair to communicate with the plugin
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		return nil, err
	}
	hostFile := os.NewFile(uintptr(fds[0]), fmt.Sprintf("host-%s", p.name))
	pluginFile := os.NewFile(uintptr(fds[1]), fmt.Sprintf("plugin-%s", p.name))

	fileConn, err := net.FileConn(hostFile)
	hostFile.Close()
	if err != nil {
		return nil, err
	}

	p.conn, err = grpc.NewClient("passthrough:///",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return fileConn, nil
		},
		))
	return pluginFile, nil
}

func (p *BasePlugin) postStart() {
	p.running = true
	p.start = time.Now().UnixMilli()
}

func (p *BasePlugin) Name() string {
	return p.name
}

func (p *BasePlugin) Target() string {
	return p.target
}

func (p *BasePlugin) Runtime() PluginRuntime {
	return p.runtime
}

func (p *BasePlugin) IsRunning() bool {
	return p.running
}

func (p *BasePlugin) Conn() *grpc.ClientConn {
	return p.conn
}

var _ Plugin = (*ProcessPlugin)(nil)
var _ Plugin = (*ContainerPlugin)(nil)
