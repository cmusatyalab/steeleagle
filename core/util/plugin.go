package util

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Plugin defines the behavior required of all plugin implementations.
type Plugin interface {
	// Start launches the plugin and returns a listener for the plugin's server
	// side and a client connection to the plugin. The returned listener
	// and connection are both bound to the plugin's lifetime. Canceling ctx
	// or calling Stop tears them down.
    Start(context.Context) (net.Listener, *grpc.ClientConn, error)

	// Stop cancels the plugin's context, triggering shutdown.
    Stop()

	// Watch returns a channel that receives the plugin's exit error when it
	// terminates.
    Watch() <-chan error

	// Wait blocks until the plugin process exits and returns its exit error.
    Wait() error

    Name() string
}

// BasePlugin provides common attributes shared across all plugins. It is
// intended to be embedded in concrete plugin structs to promote its fields.
type BasePlugin struct {
	name    string
	path    string   // path to plugin
    rdir    string   // runtime directory path
    runner  string   // runner target (e.g. bwrap, podman)
    rargs   []string // runner args
	exec    string   // executable target (e.g. sh)
	eargs   []string // executable args
	script  string   // script target (actual script)
	sargs   []string // script args
	start   int64    // plugin start time
    server  bool     // whether or not the plugin hosts a server
    timout  int      // timeout in seconds waiting for the server to start
	running bool	 // whether the plugin is currently running
	code    AuthCode // authentication level
	cmd     *exec.Cmd // command to run
    ctx     context.Context // context
    cancel  context.CancelFunc // cancellation function
}

// CreateBasePlugin creates an instance of a BasePlugin.
func CreateBasePlugin(options ...PluginOption) BasePlugin {
	// Set default input options and retrieve options
	p := BasePlugin{
		code: UnknownCode,
        name: uuid.New().String(),
	}
	for _, option := range options {
		option(&p)
	}

	return p
}

func (p *BasePlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
    // Create a new context with a cancel function
    p.ctx, p.cancel = context.WithCancel(ctx)

    // Set a target

	// Create the command
    finalExec := ""
    finalArgs := []string{}
    if p.script != "" {
		p.cmd.Dir = filepath.Dir(p.script) // change to script dir
        finalExec = p.script
        finalArgs = p.sargs
    }
    if p.exec != "" {
        finalExec = p.exec
        finalArgs = append(p.eargs, finalArgs...)
    }
    if p.runner != "" {
        finalExec = p.runner
        finalArgs = append(p.rargs, finalArgs...)
    }
	p.cmd = exec.CommandContext(ctx, finalExec, finalArgs...)
    // TODO: debug log here about starting the command

	// Reverse the listener and client; the plugin connects
	// in the opposite way
	p.cmd.Env = append(os.Environ(),
		fmt.Sprintf("%s=%s", ListenSockEnv, //TODO),
		fmt.Sprintf("%s=%s", ClientSockEnv, //TODO),
	)
	err = p.run()
	if err != nil {
		return nil, nil, err
	}

    // Cleanup goroutine
    go func() {
        <-ctx.Done()
        p.cleanup()
    }()

    return p.createSocketEndpoints()
}

func (p *BasePlugin) Stop() {
    if p.cancel != nil {
        p.cancel()
    }
}

func (p *BasePlugin) Watch() <-chan error {
	ch := make(chan error, 1)
	go func() {
		ch <- p.cmd.Wait()
	}()
	return ch
}

func (p *BasePlugin) Wait() error {
    return p.cmd.Wait()
}

func (p *BasePlugin) Name() string {
	return p.name
}

func (p *BasePlugin) setTarget() error {
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
	if info.IsDir() {
		// Set info and target to the runhook
		p.script = filepath.Join(p.path, runhook)
		info, err = os.Stat(p.script)
		if err != nil {
			p.logError(err, "couldn't stat plugin run hook, is it there?")
			return err
		}
		p.target = "sh"
	} else {
		p.script = p.path
		// Ensure that the script is runnable
		if info.Mode() & 0o111 == 0 {
			return fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", p.path)
		}
	}

	return nil
}

func (p *BasePlugin) createSocketEndpoints() (net.Listener, *grpc.ClientConn, error) {
    // Listen on the server socket
	ln, err := net.Listen("unix", p.lnFile.Name())
	if err != nil {
		log.Error().Err(err).Msg("couldn't listen on domain socket")
		return nil, nil, err
	}

	// Connect to the client socket
    target := fmt.Sprintf("unix:%s", p.cFile.Name())
    client, err := grpc.NewClient(
		target,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.Error().Err(err).Msg("couldn't connect client to domain socket")
		ln.Close()
		return nil, nil, err
	}

    acl := GetACL([]string{}, []int{p.cmd.Process.Pid})
	return NewCodedListener(ln, p.code, acl), client, nil
}

func (p *BasePlugin) cleanup() {
    p.cFile.Close()
    p.lnFile.Close()
    p.cancel()
}

func (p *BasePlugin) run() error {
	// Run the plugin
	if err := p.cmd.Start(); err != nil {
		p.logError(err, "couldn't run target for plugin")
		return err
	}

	// Populate the plugin information
	p.start = time.Now().UnixMilli()
	p.running = true

	return nil
}

func (p *BasePlugin) logError(err error, message string) {
	log.Error().Err(err).Str("plugin", p.path).Str("code", string(p.code)).Msg(message)
}
