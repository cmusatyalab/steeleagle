package util

import (
    "context"
	"os/exec"
    "net"
    "errors"
    "syscall"

	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type SandboxPlugin struct {
	Plugin
}

func CreateSandboxPlugin(options ...PluginOption) SandboxPlugin {
	// Create the plugin
	p := SandboxPlugin{
		Plugin: CreatePlugin(options...),
	}

	return p
}

func (p *SandboxPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Make sure bubblewrap is installed
	_, err := exec.LookPath("bwrap")
	if err != nil {
		log.Error().Err(err).Msg("couldn't find bubblewrap (bwrap), have you installed it?")
		return nil, nil, err
	}

	// Add the correct bubblewrap permissions
	p.args = append(p.args,
		"--ro-bind", "/usr", "/usr",
		"--ro-bind", "/lib", "/lib",
		"--ro-bind", "/lib64", "/lib64",
		"--ro-bind", "/bin", "/bin",
		"--proc", "/proc",
		"--dev", "/dev",
		"--unshare-all",
		"--die-with-parent",
	)

	if err = p.Plugin.SetTarget(); err != nil {
		return nil, nil, err
	}
	p.args = append(p.args, "--ro-bind", p.target, p.target, p.target)
	// Overwrite target to be bubblewrap
	p.target = "bwrap"

    l, c, err := p.Plugin.Spawn(ctx)
    if err != nil {
        if errors.Is(err, syscall.EACCES) {
            log.Error().Err(err).Msg("bubblewrap (bwrap) has insufficient permissions, likely due to AppArmor (see: https://developers.openai.com/codex/concepts/sandboxing)")
        }
    }
    return l, c, err
}
