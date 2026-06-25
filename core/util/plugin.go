package util

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
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
}

// BasePlugin provides common attributes shared across all plugins. It is
// intended to be embedded in concrete plugin structs to promote its fields.
type BasePlugin struct {
	id      string             // auto-generated ID for path disambiguation
	code    AuthCode           // authentication entity
	pkg     bool               // determines whether the plugin is a package or not
	path    string             // path to plugin
	runner  string             // runner target (e.g. bwrap, podman)
	rargs   []string           // runner args
	exec    string             // executable target (e.g. sh)
	eargs   []string           // executable args
	script  string             // script target (plugin script)
	sargs   []string           // script args
	files   map[string]int     // linked files (only applicable to sandboxes/containers)
	start   int64              // plugin start time
	timeout int                // timeout in seconds waiting for the server to start
	running bool               // whether or not the plugin is currently running
	runDir  string             // runtime directory path
	cSock   string             // client socket file path
	lnSock  string             // listener socket file path
	server  bool               // whether or not the plugin hosts a server
	check   bool               // whether or not to check existence of files
	cmd     *exec.Cmd          // command to run
	ctx     context.Context    // context
	cancel  context.CancelFunc // cancellation function
}

// CreateBasePlugin creates an instance of a BasePlugin.
func CreateBasePlugin(options ...PluginOption) (*BasePlugin, error) {
	// Set default input options and retrieve options
	p := &BasePlugin{
		code:    UnknownCode,
		id:      uuid.New().String(),
		files:   make(map[string]int),
		server:  true,
		check:   true,
		timeout: 15, // default to 15s timeout
	}
	for _, option := range options {
		option(p)
	}

	// Find and validate script if checks are on
	if p.check {
		err := p.validateScript()
		if err != nil {
			p.logError(err, "couldn't find a script")
			return nil, err
		}
	}

	// Get the plugin dir, then create the socket file paths
	dir, err := GetPluginDirByID(p.id)
	if err != nil {
		p.logError(err, "couldn't create plugin run directory")
		return nil, err
	}
	p.runDir = dir
	p.cSock = filepath.Join(p.runDir, clientSockName)
	p.lnSock = filepath.Join(p.runDir, listenSockName)

	return p, nil
}

// Start builds the command from the configured runner/executable/script chain, launches the subprocess,
// and returns the listener and gRPC client connection.
func (p *BasePlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Create a new context with a cancel function
	p.ctx, p.cancel = context.WithCancel(ctx)

	// Create the command; check in sequence whether the script,
	// executable, and then runner are set, and prepend the arguments
	// for each into one executable string
	final := []string{}
	if p.script != "" {
		final = slices.Insert(p.sargs, 0, p.script)
	}
	if p.exec != "" {
		final = append(p.eargs, final...)
		final = slices.Insert(final, 0, p.exec)
	}
	if p.runner != "" {
		final = append(p.rargs, final...)
		final = slices.Insert(final, 0, p.runner)
	}

	// Check for argument count
	if len(final) >= 2 {
		p.cmd = exec.CommandContext(ctx, final[0], final[1:]...)
	} else if len(final) == 1 {
		p.cmd = exec.CommandContext(ctx, final[0])
	} else {
		err := fmt.Errorf("no arguments provided to plugin")
		p.logError(err, "insufficient arguments to start plugin")
		return nil, nil, err
	}
	if p.script != "" {
		// Set the working directory for the command
		p.cmd.Dir = filepath.Dir(p.script)
	}
	p.logDebug(fmt.Sprintf("starting: %v", final))

	// Bind in stdout and stderr
	p.cmd.Stdout = os.Stdout
	p.cmd.Stderr = os.Stderr

	// Reverse the listener and client; the plugin connects
	// in the opposite way
	p.cmd.Env = append(os.Environ(),
		fmt.Sprintf("%s=%s", ListenSockEnv, p.cSock),
		fmt.Sprintf("%s=%s", ClientSockEnv, p.lnSock),
	)
	err := p.run()
	if err != nil {
		p.logError(err, "error running command")
		return nil, nil, err
	}

	// Cleanup goroutine
	go func() {
		<-p.ctx.Done()
		p.cleanup()
	}()

	return p.createSocketEndpoints()
}

// Stop cancels the plugin's context, signaling the subprocess to shut down.
func (p *BasePlugin) Stop() {
	if p.cancel != nil {
		p.cancel()
	}
}

// Watch returns a channel that receives the subprocess exit error when the process terminates.
func (p *BasePlugin) Watch() <-chan error {
	ch := make(chan error, 1)
	go func() {
		ch <- p.cmd.Wait()
	}()
	return ch
}

// Wait blocks until the plugin subprocess exits and returns its exit error.
func (p *BasePlugin) Wait() error {
	return p.cmd.Wait()
}

// validateScript resolves and validates the plugin's script path, setting pkg and exec fields as needed.
func (p *BasePlugin) validateScript() error {
	// Check if script has already been manually set
	if p.script != "" {
		_, err := os.Stat(p.script)
		if err != nil {
			p.logError(err, "couldn't stat plugin script, is it there?")
			return err
		}
		return nil
	}

	// Make sure the plugin path exists
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
		p.pkg = true
		p.script = filepath.Join(p.path, runHook)
		info, err = os.Stat(p.script)
		if err != nil {
			p.logError(err, "couldn't stat plugin run hook, is it there?")
			return err
		}
		p.exec = "sh"
	} else {
		p.script = p.path
		// Ensure that the script is runnable
		if info.Mode()&0o111 == 0 {
			p.logError(nil, "couldn't find runnable script")
			return fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", p.path)
		}
	}

	return nil
}

// createSocketEndpoints listens on the server socket and, when server mode is enabled, dials the client socket.
func (p *BasePlugin) createSocketEndpoints() (net.Listener, *grpc.ClientConn, error) {
	// Listen on the server socket
	ln, err := net.Listen("unix", p.lnSock)
	if err != nil {
		p.logError(err, "couldn't listen on socket")
		return nil, nil, err
	}

	// Wait on the socket file to be created by the plugin
	var client *grpc.ClientConn
	if p.server {
		err = p.waitForSocket(p.cSock)
		if err != nil {
			p.logError(err, "timed out waiting for socket")
			ln.Close()
			return nil, nil, err
		}

		// Connect to the client socket
		target := fmt.Sprintf("unix://%s", p.cSock)
		client, err = grpc.NewClient(
			target,
			grpc.WithTransportCredentials(insecure.NewCredentials()),
		)
		if err != nil {
			p.logError(err, "couldn't connect with client")
			ln.Close()
			return nil, nil, err
		}
	}

	acl := GetACL([]string{}, []int{p.cmd.Process.Pid})
	return NewCodedListener(ln, p.code, acl), client, nil
}

// waitForSocket polls path until the socket file exists or the plugin timeout elapses.
func (p *BasePlugin) waitForSocket(path string) error {
	deadline := time.Now().Add(time.Duration(p.timeout) * time.Second)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(path); err == nil {
			return nil
		}
		time.Sleep(50 * time.Millisecond)
	}
	return fmt.Errorf("timed out waiting for socket: %s", path)
}

// cleanup removes the plugin's runtime directory.
func (p *BasePlugin) cleanup() {
	// Remove the plugin run directory
	err := os.RemoveAll(p.runDir)
	if err != nil {
		p.logError(err, "got error while trying to clean up")
	}
}

// run starts the plugin command and records the start time.
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

// logDebug emits a debug log event annotated with the plugin ID, path, and auth code.
func (p *BasePlugin) logDebug(message string) {
	log.Debug().Str("plugin", p.id).Str("path", p.path).Str("code", string(p.code)).Msg(message)
}

// logError emits an error log event annotated with the plugin ID, path, and auth code.
func (p *BasePlugin) logError(err error, message string) {
	log.Error().Err(err).Str("plugin", p.id).Str("path", p.path).Str("code", string(p.code)).Msg(message)
}
