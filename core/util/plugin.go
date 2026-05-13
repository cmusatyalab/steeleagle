package util

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type Plugin interface {
	Name() string
	Runtime() PluginRuntime
	Spawn(context.Context) (net.Listener, *grpc.ClientConn, error)
	Stop() error
	IsRunning() bool
	Target() string
	Conn() *grpc.ClientConn
}

type BasePlugin struct {
	name    string
	target  string
	runtime PluginRuntime
	start   int64 // plugin start time
	running bool
	code    AuthCode
	cmd     *exec.Cmd
	conn    *grpc.ClientConn
}

type ProcessPlugin struct {
	BasePlugin
}

type ContainerPlugin struct {
	BasePlugin
	cid string
	tag string
}

func CreateProcessPlugin(code AuthCode, name, target string) (*ProcessPlugin, error) {
	// Check that the process target exists
	info, err := os.Stat(target)
	if err != nil {
		if os.IsNotExist(err) {
			log.Error().Err(err).Str("name", name).Str("code", string(code)).Msg("couldn't find plugin, have you installed it?")
			return nil, err
		}
		log.Error().Err(err).Str("name", name).Str("code", string(code)).Msg("couldn't stat plugin target")
		return nil, err
	}

	// If the plugin is a directory, then attach the runhook
	if info.IsDir() {
		// Set info and target to the runhook
		target = filepath.Join(target, runhook)
		info, err = os.Stat(target)
		if err != nil {
			log.Error().Err(err).Str("name", name).Str("code", string(code)).Msg("couldn't stat plugin run hook, is it there?")
		}
	}
	// Ensure that the plugin is runnable
	if info.Mode()&0o111 == 0 {
		return nil, fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", name)
	}

	// Create the plugin
	p := &ProcessPlugin{
		BasePlugin: BasePlugin{
			name:    name,
			target:  target,
			runtime: Process,
			code:    code,
		},
	}

	return p, nil
}

func CreateContainerPlugin(code AuthCode, name, target, tag string) (*ContainerPlugin, error) {
	// Make sure podman is installed
	target, err := exec.LookPath("podman")
	if err != nil {
		log.Error().Err(err).Msg("couldn't find podman, have you installed it?")
		return nil, err
	}

	// Check whether the image exists
	err = exec.Command("podman", "image", "exists", tag).Run()
	if err != nil {
		log.Error().Err(err).Msg("couldn't run image check with podman")
		return nil, err
	}
	if exitErr, ok := err.(*exec.ExitError); ok {
		if exitErr.ExitCode() == 1 {
			return nil, fmt.Errorf("container image %s not found", tag)
		}
	}

	// Create the command and plugin
	p := &ContainerPlugin{
		BasePlugin: BasePlugin{
			name:    name,
			runtime: Container,
			code:    code,
		},
		tag: tag,
	}

	return p, nil
}

func (p *ProcessPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Create the command
	p.cmd = exec.CommandContext(ctx, p.target)

	// Run the plugin
	ln, c, err := p.spawnAndCreateConns()

	// Populate the plugin information
	p.start = time.Now().UnixMilli()
	p.running = true

	return ln, c, err
}

func (p *ProcessPlugin) Stop() error {
	return nil
}

func (p *ContainerPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Write container id to a temporary file so it can be read
	cidFile, _ := os.CreateTemp("", "cid-*")
	cidFile.Close()
	defer os.Remove(cidFile.Name())

	// Create the command
	p.cmd = exec.CommandContext(ctx, "podman", "run", "--rm",
		"--cidfile", cidFile.Name(),
		"--preserve-fd", "3",
		p.tag)

	// Run the plugin
	ln, c, err := p.spawnAndCreateConns()

	// Get container id from the temporary file
	data, _ := os.ReadFile(cidFile.Name())
	p.cid = strings.TrimSpace(string(data))
	p.start = time.Now().UnixMilli()
	p.running = true

	return ln, c, err
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

func (p *BasePlugin) spawnAndCreateConns() (net.Listener, *grpc.ClientConn, error) {
	// Create a socket pair to communicate with the plugin
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't open socket pair for plugin")
		return nil, nil, err
	}

	// Create internal files
	ln := os.NewFile(uintptr(fds[0]), fmt.Sprintf("listener-%s", p.name))
	client := os.NewFile(uintptr(fds[1]), fmt.Sprintf("client-%s", p.name))
	defer ln.Close()
	defer client.Close()
	p.cmd.ExtraFiles = []*os.File{client}

	// Build the file connections
	lnConn, err := net.FileConn(ln)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't open listener socket")
		return nil, nil, err
	}
	clientConn, err := net.FileConn(ln)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't open client socket")
		return nil, nil, err
	}
	spClient, err := NewSocketPairClient(clientConn)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't create socket pair client")
		return nil, nil, err
	}
	p.conn = spClient

	// Run target
	if err := p.cmd.Run(); err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't run target for plugin")
		return nil, nil, err
	}

	return NewSocketPairListener(lnConn, p.code), spClient, nil
}
