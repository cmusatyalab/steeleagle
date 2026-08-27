package util

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Plugin defines the behavior required of all plugin implementations.
type Plugin interface {
	// Start launches the plugin and returns a listener for the plugin's server
	// side and a client connection to the plugin. The returned listener and
	// connection are both bound to the plugin's lifetime. Canceling ctx or
	// calling Stop tears them down.
	Start(context.Context) (net.Listener, *grpc.ClientConn, error)

	// Watch returns a channel that receives the plugin's exit error when it
	// terminates.
	Watch() <-chan error

	// Wait blocks until the plugin process exits and returns its exit error.
	Wait() error

	// Name gets the readable name of the plugin.
	Name() string

	// Code gets the AuthCode of the plugin.
	Code() AuthCode
}

// BasePlugin provides common attributes shared across all plugins. It is
// intended to be embedded in concrete plugin structs to promote its fields.
type BasePlugin struct {
	name        string             // name for easier user identification
	code        AuthCode           // authentication entity
	pkg         bool               // determines whether the plugin is a package or not
	path        string             // path to plugin
	runner      string             // runner target (e.g. bwrap, podman)
	final       []string           // final args for the subprocess
	rargs       []string           // runner args, never modified during runtime
	exec        string             // executable target (e.g. sh)
	eargs       []string           // executable args
	script      string             // script target (plugin script)
	sargs       []string           // script args
	files       map[string]int     // linked files (only applicable to sandboxes/containers)
	start       int64              // plugin start time
	timeout     int                // timeout in seconds waiting for the server to start
	running     atomic.Bool        // whether or not the plugin is currently running
	parentDir   string             // parent directory for plugin to live under (used to create runDir)
	runDir      string             // runtime directory path
	cSock       string             // path of the socket this process dials as a client, and the plugin listens on
	lnSock      string             // path of the socket this process listens on, and the plugin dials as a client
	client      bool               // whether or not to support a plugin server
	listen      bool               // whether or not to support a plugin client
	check       bool               // whether or not to check existence of files
	cmd         *exec.Cmd          // command to run
	acl         *ACL               // ACL for listener connections
	log         zerolog.Logger     // logger object
	outStream   io.Writer          // replacement out file for Stdout/err
	environ     []string           // environment to run the plugin in
	ctx         context.Context    // context
	cancel      context.CancelFunc // cancellation function
	waitOnce    sync.Once          // guards against calling cmd.Wait() more than once
	waitErr     error              // result of cmd.Wait(), populated exactly once by waitOnce
	waitDone    chan struct{}      // closed once cmd exits, indicates waitErr is ready to read
	cleanupDone chan struct{}      // closed once cleanup() finishes running for the current Start()
}

// CreateBasePlugin creates an instance of a BasePlugin.
func CreateBasePlugin(options ...PluginOption) (*BasePlugin, error) {
	// Set defaults
	p := &BasePlugin{
		name:      uuid.New().String(),
		code:      UnknownCode,
		files:     make(map[string]int),
		client:    true,
		listen:    true,
		check:     true,
		timeout:   15, // default to 15s timeout
		log:       zerolog.New(os.Stdout).With().Timestamp().Logger(),
		outStream: os.Stdout,
		environ:   os.Environ(),
	}
	// Apply options
	for _, option := range options {
		option(p)
	}

	p.log = p.log.With().Str("plugin", p.name).Logger()

	// Create a new ACL if it isn't initialized
	if p.acl == nil {
		p.acl = GetACL([]string{}, []int{})
	}

	// Find and validate script if checks are on
	if p.check {
		err := p.validateScript()
		if err != nil {
			p.log.Error().Err(err).Msg("couldn't find a script")
			return nil, err
		}
	}

	return p, nil
}

// Start builds the command from the configured runner/executable/script chain,
// launches the subprocess, and returns the listener and gRPC client
// connection.
func (p *BasePlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Prevent against multiple Start() calls while running
	if !p.running.CompareAndSwap(false, true) {
		return nil, nil, fmt.Errorf("plugin already running")
	}

	// Create a new context with a cancel function
	p.ctx, p.cancel = context.WithCancel(ctx)

	// Reset the per-run wait/cleanup state so a restarted plugin waits on its
	// new process rather than replaying the previous run's result.
	p.waitOnce = sync.Once{}
	p.waitErr = nil
	p.waitDone = make(chan struct{})
	p.cleanupDone = make(chan struct{})

	// Set up the run directory and the client/listen socket
	err := p.setupRunDir()
	if err != nil {
		p.log.Err(err).Msg("error setting up plugin runtime directory")
		p.cleanup()
		return nil, nil, err
	}

	// Create the command if it hasn't already been created; check in sequence
	// whether the script, executable, and then runner are set, and prepend the
	// arguments for each into one executable string
	if p.final == nil {
		if p.script != "" {
			p.final = slices.Insert(p.sargs, 0, p.script)
		}
		if p.exec != "" {
			p.final = append(p.eargs, p.final...)
			p.final = slices.Insert(p.final, 0, p.exec)
		}
		if p.runner != "" {
			p.final = append(p.rargs, p.final...)
			p.final = slices.Insert(p.final, 0, p.runner)
		}
	}

	// Check for argument count
	if len(p.final) >= 2 {
		p.cmd = exec.CommandContext(ctx, p.final[0], p.final[1:]...)
	} else if len(p.final) == 1 {
		p.cmd = exec.CommandContext(ctx, p.final[0])
	} else {
		err := fmt.Errorf("no arguments provided to plugin")
		p.log.Error().Err(err).Msg("insufficient arguments to start plugin")
		p.cleanup()
		return nil, nil, err
	}
	// Run in its own process group and kill the whole group on shutdown, not
	// just the immediate child
	p.cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	p.cmd.Cancel = func() error {
		return syscall.Kill(-p.cmd.Process.Pid, syscall.SIGKILL)
	}
	if p.script != "" {
		// Set the working directory for the command
		p.cmd.Dir = filepath.Dir(p.script)
	}
	p.log.Info().Msgf("starting: %v", p.final)

	// Bind in stdout and stderr
	p.cmd.Stdout = p.outStream
	p.cmd.Stderr = p.outStream

	// Reverse the listener and client; the plugin connects in the opposite way
	p.cmd.Env = append(
		p.environ,
		fmt.Sprintf("%s=%s", ListenSockEnv, p.cSock),
		fmt.Sprintf("%s=%s", ClientSockEnv, p.lnSock),
	)
	err = p.run()
	if err != nil {
		p.log.Error().Err(err).Msg("error running command")
		p.cleanup()
		return nil, nil, err
	}
	p.log.Info().Int("pid", p.cmd.Process.Pid).Msg("plugin process launched")
	p.acl.AddPID(p.cmd.Process.Pid)

	// Cleanup goroutine.
	go func() {
		err := p.waitProcess()
		if ctx.Err() != nil {
			p.log.Err(err).Msg("context canceled, initiating cleanup")
		} else {
			var exitErr *exec.ExitError
			if errors.As(err, &exitErr) {
				p.log.Err(err).
					Msgf("plugin exited unexpectedly with exit code %d", exitErr.ExitCode())
			}
		}
		p.cleanup()
	}()

	return p.createSocketEndpoints()
}

// Watch returns a channel that receives the subprocess exit error when the
// process terminates.
func (p *BasePlugin) Watch() <-chan error {
	if p.cmd == nil {
		return nil
	}
	ch := make(chan error, 1)
	go func() { ch <- p.Wait() }()
	return ch
}

// Wait blocks until the plugin subprocess exits and its cleanup has finished,
// then returns the subprocess's exit error. Callers can safely Start() the
// plugin again once Wait() returns.
func (p *BasePlugin) Wait() error {
	if p.cmd == nil {
		return nil
	}
	err := p.waitProcess()
	<-p.cleanupDone
	return err
}

// waitProcess blocks until the plugin subprocess exits and returns its exit
// error.
func (p *BasePlugin) waitProcess() error {
	if !p.running.Load() {
		return fmt.Errorf("plugin not running")
	}
	if p.cmd == nil {
		return nil
	}
	p.waitOnce.Do(func() {
		p.waitErr = p.cmd.Wait()
		if p.ctx.Err() != nil {
			p.waitErr = p.ctx.Err()
		}
		close(p.waitDone)
	})
	<-p.waitDone
	return p.waitErr
}

// Name gets the readable name of the plugin.
func (p *BasePlugin) Name() string {
	return p.name
}

// Code gets the AuthCode of the plugin.
func (p *BasePlugin) Code() AuthCode {
	return p.code
}

// validateScript resolves and validates the plugin's script path, setting pkg
// and exec fields as needed.
func (p *BasePlugin) validateScript() error {
	// Check if script has already been manually set
	if p.script != "" {
		_, err := os.Stat(p.script)
		if err != nil {
			p.log.Error().Err(err).Msg("couldn't stat plugin script, is it there?")
			return err
		}
		return nil
	}

	// Make sure the plugin path exists
	info, err := os.Stat(p.path)
	if err != nil {
		if os.IsNotExist(err) {
			p.log.Error().Err(err).Msg("couldn't find plugin, have you installed it?")
			return err
		}
		p.log.Error().Err(err).Msg("couldn't stat plugin path")
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
			p.log.Error().Err(err).Msg("couldn't stat plugin run hook, is it there?")
			return err
		}
		p.exec = "sh"
	} else {
		p.script = p.path
		// Ensure that the script is runnable
		if info.Mode()&0o111 == 0 {
			p.log.Error().Msg("couldn't find runnable script")
			return fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", p.path)
		}
	}

	return nil
}

// createSocketEndpoints listens on the server socket and, when server mode is
// enabled, dials the client socket.
func (p *BasePlugin) createSocketEndpoints() (net.Listener, *grpc.ClientConn, error) {
	var err error
	var listen net.Listener
	if p.listen {
		// Listen on the server socket
		listen, err = net.Listen("unix", p.lnSock)
		if err != nil {
			p.log.Error().Err(err).Msg("couldn't listen on socket")
			return nil, nil, err
		}
	}

	// Wait on the socket file to be created by the plugin
	var client *grpc.ClientConn
	if p.client {
		p.log.Info().Int("timeout_sec", p.timeout).Str("socket", p.cSock).
			Msg("waiting for plugin to create its socket")
		err = p.waitForSocket(p.cSock)
		if err != nil {
			p.log.Error().Err(err).Msg("timed out waiting for socket")
			if listen != nil {
				listen.Close()
			}
			return nil, nil, err
		}
		p.log.Info().Msg("plugin socket ready, connecting")

		// Connect to the client socket
		target := fmt.Sprintf("unix://%s", p.cSock)
		client, err = grpc.NewClient(
			target,
			grpc.WithTransportCredentials(insecure.NewCredentials()),
		)
		if err != nil {
			p.log.Error().Err(err).Msg("couldn't connect with client")
			if listen != nil {
				listen.Close()
			}
			return nil, nil, err
		}
	}

	return NewCodedListener(listen, p.code, p.acl), client, nil
}

// waitForSocket polls path until the socket file exists or the plugin timeout
// elapses.
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

// cleanup cleans up system resources, including the runtime directory.
func (p *BasePlugin) cleanup() {
	// Remove the plugin run directory
	err := os.RemoveAll(p.runDir)
	p.cancel()
	p.running.Store(false)
	if err != nil {
		p.log.Error().Err(err).Msg("got error while trying to clean up")
	}
	close(p.cleanupDone)
}

// run starts the plugin command and records the start time.
func (p *BasePlugin) run() error {
	// Run the plugin
	if err := p.cmd.Start(); err != nil {
		p.log.Error().Err(err).Msg("couldn't run target for plugin")
		return err
	}

	// Populate the plugin information
	p.start = time.Now().UnixMilli()

	return nil
}

func (p *BasePlugin) setupRunDir() error {
	// Get the plugin dir, then create the socket file paths
	dir, err := GetPluginDirByName(p.name, p.parentDir)
	if err != nil {
		p.log.Error().Err(err).Msg("couldn't create plugin run directory")
		return err
	}
	p.runDir = dir
	p.cSock = filepath.Join(p.runDir, clientSockName)
	p.lnSock = filepath.Join(p.runDir, listenSockName)
	// Remove socket paths in case they're left over from last run
	os.Remove(p.cSock)
	os.Remove(p.lnSock)
	return nil
}
