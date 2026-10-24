package plugin

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"

	"google.golang.org/grpc"
)

type SandboxPlugin struct {
	*BasePlugin
	prepared bool // whether the bwrap args have been added to rargs
}

// NewSandboxPlugin creates a SandboxPlugin backed by bubblewrap (bwrap).
func NewSandboxPlugin(options ...PluginOption) (*SandboxPlugin, error) {
	// Create the plugin
	internal, err := NewBasePlugin(options...)
	if err != nil {
		return nil, err
	}
	p := &SandboxPlugin{
		BasePlugin: internal,
	}
	p.runner = "bwrap"

	// Make sure bubblewrap is installed
	_, err = exec.LookPath("bwrap")
	if err != nil {
		p.log.Error().Err(err).Msg("couldn't find bubblewrap (bwrap), have you installed it?")
		return nil, err
	}

	// Make sure bubblerap has the right permissions
	err = checkBwrapPermissions()
	if err != nil {
		p.log.Error().Err(err).Msg("bubblewrap couldn't run")
		return nil, err
	}

	// Package plugins are started with pixi, so make sure it is available
	// within the sandbox
	if p.pkg && p.exec == pixiExec {
		if _, ok := p.files[pixiExec]; !ok {
			p.files[pixiExec] = 2
		}
	}

	return p, nil
}

// Start delegates to BasePlugin.Start.
func (p *SandboxPlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	if err := p.createSandbox(); err != nil {
		p.log.Error().Err(err).Msg("failed to create sandbox")
		return nil, nil, err
	}
	return p.BasePlugin.Start(ctx)
}

// createSandbox sets up the script to run inside a bwrap sandbox.
func (p *SandboxPlugin) createSandbox() error {
	// Don't modify the args out from under a running sandbox
	if p.running.Load() {
		return fmt.Errorf("plugin already running")
	}
	// Check if the sandbox args have been set up, if so nothing needs to be
	// done
	if p.prepared {
		return nil
	}

	// Setup the run directory
	err := p.setupRunDir()
	if err != nil {
		p.log.Err(err).Msg("error setting up plugin runtime directory")
		return err
	}

	// Add the correct bubblewrap args
	args := []string{
		"--unshare-all",
		"--ro-bind", "/usr", "/usr",
		"--ro-bind", "/lib", "/lib",
		"--ro-bind", "/lib64", "/lib64",
		"--ro-bind", "/bin", "/bin",
		"--bind", p.runDir, p.runDir,
		"--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
		"--ro-bind", "/etc/nsswitch.conf", "/etc/nsswitch.conf",
		// CA certificates and a temp directory are required by pixi
		"--ro-bind-try", "/etc/ssl", "/etc/ssl",
		"--ro-bind-try", "/etc/ca-certificates", "/etc/ca-certificates",
		"--ro-bind-try", "/etc/pki", "/etc/pki",
		"--tmpfs", "/tmp",
		"--proc", "/proc",
		"--dev", "/dev",
		"--die-with-parent",
	}

	// Link in files
	for f, w := range p.files {
		if w == 2 { // executables
			path, err := exec.LookPath(f)
			if err != nil {
				p.log.Error().Err(err).Msg("couldn't get path to executable")
				return err
			}
			args = append(args,
				"--ro-bind",
				path, path, // bind to exact path for executables
			)
		} else {
			_, err := os.Stat(f) // ensure the file exists
			if err != nil {
				p.log.Error().Err(err).Msg("couldn't stat linked file")
				return err
			}
			path, err := filepath.Abs(f)
			if err != nil {
				p.log.Error().Err(err).Msg("couldn't get absolute filepath")
				return err
			}
			if w == 1 { // read-write
				args = append(args,
					"--bind",
					path,
					fmt.Sprintf("/%s/%s", bindDir, filepath.Base(path)),
				)
			} else { // read-only
				args = append(args,
					"--ro-bind",
					path,
					fmt.Sprintf("/%s/%s", bindDir, filepath.Base(path)),
				)
			}
		}
	}

	// Append the existing runner args onto these args,
	// since we want to preserve any passed in args
	p.rargs = append(args, p.rargs...)

	// Only bind in the plugin files if checks are enabled,
	// otherwise blindly use the script/exec set by the user
	if p.check {
		// Bind in the plugin files
		if p.pkg {
			p.rargs = append(p.rargs,
				"--bind",
				p.path, bindDir,
				"--chdir",
				bindDir,
			)
		} else {
			p.rargs = append(p.rargs,
				"--bind",
				p.script,
				fmt.Sprintf("/%s/%s", bindDir, filepath.Base(p.script)),
				"--chdir",
				bindDir,
			)
			p.script = fmt.Sprintf("./%s", filepath.Base(p.script))
		}
	}
	p.prepared = true
	return nil
}

// checkBwrapPermissions verifies that bwrap can run a minimal sandbox, returning an error if permissions are insufficient.
func checkBwrapPermissions() error {
	// Try a minimal bwrap invocation
	cmd := exec.Command("bwrap",
		"--ro-bind", "/", "/",
		"true",
	)

	// If this command doesn't succeed, it might be due to
	// a lack of AppArmor permissions
	if _, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("bubblewrap has insufficient permissions, could be AppArmor (https://developers.openai.com/codex/concepts/sandboxing)")
	}
	return nil
}

var _ Plugin = (*SandboxPlugin)(nil)
