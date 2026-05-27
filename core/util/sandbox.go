package util

import (
    "context"
	"os/exec"
    "net"

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

func (p *SandboxPlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Make sure bubblewrap is installed
	_, err := exec.LookPath("bwrap")
	if err != nil {
		p.logError(err, "couldn't find bubblewrap (bwrap), have you installed it?")
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

    return p.Plugin.Start(ctx)
}
