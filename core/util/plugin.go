package util

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type Plugin struct {
	name    string
	path    string
	target  string // executable target
	args    []string
	start   int64 // plugin start time
	running bool
	code    AuthCode
	cmd     *exec.Cmd
}

func CreatePlugin(options ...PluginOption) Plugin {
	// Set default input options and retrieve options
	p := Plugin{
		name: uuid.New().String(),
		code: UnknownCode,
	}
	for _, option := range options {
		option(&p)
	}

	return p
}

func (p *Plugin) SetTarget() error {
	info, err := os.Stat(p.path)
	if err != nil {
		if os.IsNotExist(err) {
			p.logError(err, "couldn't find plugin, have you installed it?")
			return err
		}
		p.logError(err, "couldn't stat plugin path")
		return err
	}

	// If the plugin is a directory, then use the runhook as the
	// target executable
	var target string
	if info.IsDir() {
		// Set info and target to the runhook
		target = filepath.Join(p.path, runhook)
		info, err = os.Stat(target)
		if err != nil {
			p.logError(err, "couldn't stat plugin run hook, is it there?")
			return err
		}
	} else {
		target = p.path
	}
	// Ensure that the target is runnable
	if info.Mode()&0o111 == 0 {
		return fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", p.name)
	}

	// Assign target
	p.target = target

	return nil
}

func (p *Plugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// If target isn't already set, set it now
	if p.target == "" {
		err := p.SetTarget()
		if err != nil {
			return nil, nil, err
		}
	}

	// Get socket files, one for vehicle->plugin, one for plugin->vehicle
	ln, pc, err := CreateSocketPairFiles()
	if err != nil {
		return nil, nil, err
	}
	c, pln, err := CreateSocketPairFiles()
	if err != nil {
		return nil, nil, err
	}

	// Create the command
	p.cmd = exec.CommandContext(ctx, p.target, p.args...)
	p.cmd.ExtraFiles = []*os.File{pln, pc}

	// Run the plugin
	if err := p.cmd.Start(); err != nil {
        p.logError(err, "couldn't run target for plugin")
		return nil, nil, err
	}

	// Populate the plugin information
	p.start = time.Now().UnixMilli()
	p.running = true

	return CreateSocketPairEndpoints(p.code, ln, c)
}

func (p *Plugin) Name() string {
	return p.name
}

func (p *Plugin) Stop() error {
	return p.cmd.Process.Kill()
}

func (p *Plugin) Watch() <-chan error {
    ch := make(chan error, 1)
    go func() {
        ch <- p.cmd.Wait()
    }()
    return ch
}

func (p *Plugin) GetCommand() *exec.Cmd {
	return p.cmd
}

func (p *Plugin) logError(err error, message string) {
    log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg(message)
}
