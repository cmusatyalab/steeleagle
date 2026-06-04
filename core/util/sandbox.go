package util

import (
	"context"
	"fmt"
	"net"
	"os/exec"
	"path/filepath"

	"google.golang.org/grpc"
)

type SandboxPlugin struct {
	BasePlugin
}

func CreateSandboxPlugin(options ...PluginOption) SandboxPlugin {
	// Create the plugin
	p := SandboxPlugin{
		BasePlugin: CreateBasePlugin(options...),
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
        "--ro-bind", p.lnFile.Name(), filepath.Join(rundir, filepath.Base(p.lnFile.Name())),
        "--ro-bind", p.cFile.Name(), filepath.Join(rundir, filepath.Base(p.cFile.Name())),
		"--proc", "/proc",
		"--dev", "/dev",
		"--unshare-all",
		"--die-with-parent",
	)

	// Bind the file and set the target/script
	if err = p.BasePlugin.setTarget(); err != nil {
		return nil, nil, err
	}

	// Mount the file and set the target/script
	if p.target == "sh" && p.script != "" {
		// Runhook case
		p.args = append(p.args,
			"--ro-bind",
			p.path,
			rundir,
			"--chdir",
			rundir,
			"sh",
			filepath.Base(p.script),
		)
		// Reset script so base plugin doesn't append it
		p.script = ""
	} else if p.target != "" {
		// Binary case
		p.args = append(p.args,
			"--ro-bind",
			p.target,
			fmt.Sprintf("%s/%s", rundir, filepath.Base(p.target)),
			"--chdir",
			rundir,
			fmt.Sprintf("./%s", filepath.Base(p.target)),
		)
	} else {
		return nil, nil, fmt.Errorf("incorrectly formatted command, target is not sh and script is set")
	}
	// Overwrite target to be bubblewrap
	p.target = "bwrap"

	return p.BasePlugin.Start(ctx)
}
