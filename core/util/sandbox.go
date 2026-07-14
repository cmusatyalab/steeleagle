package util

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
}

// CreateSandboxPlugin creates a SandboxPlugin backed by bubblewrap (bwrap).
func CreateSandboxPlugin(options ...PluginOption) (*SandboxPlugin, error) {
	// Create the plugin
	internal, err := CreateBasePlugin(options...)
	if err != nil {
		return nil, nil
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

	return p, nil
}

// Start assembles the bubblewrap arguments, binds in the plugin files, and delegates to BasePlugin.Start.
func (p *SandboxPlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	err := p.setupRunDir()
	if err != nil {
		p.log.Err(err).Msg("error setting up plugin runtime directory")
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
				return nil, nil, err
			}
			args = append(args,
				"--ro-bind",
				path, path, // bind to exact path for executables
			)
		} else {
			_, err := os.Stat(f) // ensure the file exists
			if err != nil {
				p.log.Error().Err(err).Msg("couldn't stat linked file")
				return nil, nil, err
			}
			path, err := filepath.Abs(f)
			if err != nil {
				p.log.Error().Err(err).Msg("couldn't get absolute filepath")
				return nil, nil, err
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
	args = append(args, p.rargs...)

	// Only bind in the plugin files if checks are enabled,
	// otherwise blindly use the script/exec set by the user
	if p.check {
		// Bind in the plugin files
		if p.pkg {
			args = append(args,
				"--bind",
				p.path, bindDir,
				"--chdir",
				bindDir,
			)
		} else {
			args = append(args,
				"--bind",
				p.script,
				fmt.Sprintf("/%s/%s", bindDir, filepath.Base(p.script)),
				"--chdir",
				bindDir,
			)
		}
		p.script = fmt.Sprintf("./%s", filepath.Base(p.script))
	}

	p.rargsOverride = args
	return p.BasePlugin.Start(ctx)
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
