package plugin

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

	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Plugin defines the behavior required of all plugin implementations.
type Plugin interface {
	// Start runs the plugin in execution mode, which if using pixi, runs
	// `pixi run start`, or can run any arbitrary script. It returns a listener
	// for the plugin's gRPC server side and a client connection to the plugin
	// The returned listener and connection are both bound to the plugin's lifetime.
	// Cancel ctx to stop.
	Start(context.Context) (net.Listener, *grpc.ClientConn, error)

	// Watch returns a channel that receives the plugin's exit error when it
	// terminates.
	Watch() <-chan error

	// Wait blocks until the plugin process exits and returns its exit error.
	Wait() error

	// Name gets the readable name of the plugin.
	Name() string

	// Code gets the AuthCode of the plugin.
	Code() listener.AuthCode

	// Running reports whether the plugin is currently running.
	Running() bool
}

// BasePlugin provides common attributes shared across all plugins. It is
// intended to be embedded in concrete plugin structs to promote its fields.
type BasePlugin struct {
	name        string             // name for easier user identification
	code        listener.AuthCode  // authentication entity
	pkg         bool               // determines whether the plugin is a package or not
	path        string             // path to plugin
	runner      string             // runner target (e.g. bwrap, podman)
	final       []string           // final args for the most recent subprocess
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
	runDir      string             // runtime directory path (where sockets live)
	cSock       string             // path of the socket this process dials as a client, and the plugin listens on
	lnSock      string             // path of the socket this process listens on, and the plugin dials as a client
	client      bool               // whether or not to support a plugin server
	listen      bool               // whether or not to support a plugin client
	check       bool               // whether or not to check existence of files
	cmd         *exec.Cmd          // command to run
	acl         *listener.Acl      // ACL for listener connections
	pids        []int              // PIDs this plugin added to the ACL, removed on cleanup
	pidsMu      sync.Mutex         // guards pids
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

// NewBasePlugin creates an instance of a BasePlugin.
func NewBasePlugin(options ...PluginOption) (*BasePlugin, error) {
	// Set defaults
	p := &BasePlugin{
		name:      uuid.New().String(),
		code:      listener.UnknownCode,
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

	// Create a new closed ACL if it isn't initialized; only the plugin itself
	// should use its listener
	if p.acl == nil {
		p.acl = listener.NewAcl(nil, nil, false)
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

// Start starts the plugin in normal execution mode.
func (p *BasePlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	if err := p.createAndRunCommand(ctx); err != nil {
		p.log.Error().Err(err).Msg("couldn't start plugin")
		return nil, nil, err
	}
	// Add the process to the ACL so that the returned listener accepts it
	p.allowPid(p.cmd.Process.Pid)
	ln, conn, err := p.createSocketEndpoints()
	if err != nil {
		p.abort()
		return nil, nil, err
	}
	return ln, conn, nil
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

// Name gets the readable name of the plugin.
func (p *BasePlugin) Name() string {
	return p.name
}

// Code gets the AuthCode of the plugin.
func (p *BasePlugin) Code() listener.AuthCode {
	return p.code
}

// Running reports whether the plugin is currently running.
func (p *BasePlugin) Running() bool {
	return p.running.Load()
}

// buildCommand assembles the runner, executable, and script along with their
// args into one command. Pixi packages are started with `pixi <eargs> start`
// (eargs default to `run`). Fresh slices are used so that none of the
// configured arg slices are aliased or modified.
func (p *BasePlugin) buildCommand() []string {
	var args []string
	if p.runner != "" {
		args = append(args, p.runner)
		args = append(args, p.rargs...)
	}
	if p.exec != "" {
		args = append(args, p.exec)
		args = append(args, p.eargs...)
		if p.usesPixi() {
			args = append(args, pixiStart)
		}
	}
	if p.script != "" {
		args = append(args, p.script)
		args = append(args, p.sargs...)
	}
	return args
}

// createAndRunCommand builds the start command, and then runs the command with
// the input context. On success, a goroutine cleans up the plugin
// once the process exits; on failure, cleanup has already been run.
func (p *BasePlugin) createAndRunCommand(ctx context.Context) error {
	// Prevent against multiple subsequent run calls while running
	if !p.running.CompareAndSwap(false, true) {
		return fmt.Errorf("plugin already running")
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
		return err
	}

	// Rebuild the command on every run
	p.final = p.buildCommand()

	// Check for argument count
	if len(p.final) >= 2 {
		p.cmd = exec.CommandContext(p.ctx, p.final[0], p.final[1:]...)
	} else if len(p.final) == 1 {
		p.cmd = exec.CommandContext(p.ctx, p.final[0])
	} else {
		err := fmt.Errorf("no arguments provided to plugin")
		p.log.Error().Err(err).Msg("insufficient arguments to start plugin")
		p.cleanup()
		return err
	}
	// Run in its own process group and kill the whole group on shutdown, not
	// just the immediate child
	p.cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	p.cmd.Cancel = func() error {
		return syscall.Kill(-p.cmd.Process.Pid, syscall.SIGKILL)
	}
	// Run packages from the package directory, and scripts from the script's
	// directory
	if p.pkg {
		p.cmd.Dir = p.path
	} else {
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
		return err
	}
	p.log.Info().Int("pid", p.cmd.Process.Pid).Msg("plugin process launched")

	// Cleanup goroutine
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
	return nil
}

// validateScript resolves and validates the plugin's script path, setting pkg
// and exec fields as needed. Directories are treated as pixi packages, which
// are started with `pixi run start`, unless an executable has been set, in which
// case the executable and its args are used in place of `pixi run <task>`. Files
// are treated as binaries and run directly.
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

	// If the plugin is a directory, then run its pixi start task
	if info.IsDir() {
		manifest, err := findManifest(p.path)
		if err != nil {
			p.log.Error().Err(err).Msg("couldn't find pixi manifest, is it there?")
			return err
		}
		p.log.Debug().Str("manifest", manifest).Msg("found pixi manifest")
		p.pkg = true
		if p.exec == "" {
			p.exec = pixiExec
			p.eargs = slices.Insert(p.eargs, 0, pixiRun)
		}
	} else {
		p.script = p.path
		// Ensure that the script is runnable
		if info.Mode()&0o111 == 0 {
			p.log.Error().Msg("couldn't find runnable script")
			return fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", p.path)
		}
		p.log.Debug().Str("script", p.script).Msg("found executable script")
	}

	return nil
}

// abort kills a launched plugin process and blocks until its cleanup has
// finished, so that a failed Start never leaves the process running and the
// plugin can be started again as soon as abort returns.
func (p *BasePlugin) abort() {
	p.cancel()
	p.Wait()
}

// findManifest returns the path of the pixi manifest within dir.
func findManifest(dir string) (string, error) {
	for _, name := range pixiManifests {
		manifest := filepath.Join(dir, name)
		if _, err := os.Stat(manifest); err == nil {
			return manifest, nil
		}
	}
	return "", fmt.Errorf("plugin %s does not contain a pixi manifest (one of %v)", dir, pixiManifests)
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

	if listen == nil {
		return nil, client, nil
	}
	return listener.NewCodedListener(listen, p.acl, listener.WithLogger(p.log)), client, nil
}

// waitForSocket polls path until the socket file exists, the plugin process
// exits, or the plugin timeout elapses.
func (p *BasePlugin) waitForSocket(path string) error {
	deadline := time.Now().Add(time.Duration(p.timeout) * time.Second)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(path); err == nil {
			return nil
		}
		select {
		case <-p.waitDone: // nil for shims, which never select this case
			return fmt.Errorf("plugin exited before creating socket: %s", path)
		default:
		}
		time.Sleep(50 * time.Millisecond)
	}
	return fmt.Errorf("timed out waiting for socket: %s", path)
}

// allowPid adds pid to the ACL with the plugin's AuthCode, and records it so
// that it is removed from the ACL on cleanup.
func (p *BasePlugin) allowPid(pid int) {
	p.pidsMu.Lock()
	defer p.pidsMu.Unlock()
	if err := p.acl.AddPid(pid, p.code); err != nil {
		p.log.Error().Err(err).Int("pid", pid).Msg("couldn't add pid to acl")
		return
	}
	p.pids = append(p.pids, pid)
}

// cleanup cleans up system resources, including the runtime directory and the
// PIDs this plugin added to the ACL.
func (p *BasePlugin) cleanup() {
	// Remove the plugin's PIDs from the ACL, since they may be reused by
	// unrelated processes once the plugin exits
	p.pidsMu.Lock()
	for _, pid := range p.pids {
		p.acl.RemovePid(pid)
	}
	p.pids = nil
	p.pidsMu.Unlock()

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
	dir, err := util.GetPluginDirByName(p.name, p.parentDir)
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

// usesPixi reports whether the plugin is a package run through a pixi task.
func (p *BasePlugin) usesPixi() bool {
	return p.pkg && p.exec == pixiExec
}
