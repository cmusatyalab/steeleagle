package util

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os/exec"
	"path/filepath"

	"google.golang.org/grpc"
)

type ContainerPlugin struct {
	Plugin
	tag string
}

func CreateContainerPlugin(tag string, options ...PluginOption) ContainerPlugin {
	// Create the plugin
	p := ContainerPlugin{
		Plugin: CreatePlugin(options...),
		tag:    tag,
	}

	return p
}

func (p *ContainerPlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Make sure podman is installed
	_, err := exec.LookPath("podman")
	if err != nil {
		p.logError(err, "couldn't find podman, have you installed it?")
		return nil, nil, err
	}

	// Check whether the image exists
	err = exec.Command("podman", "image", "exists", p.tag).Run()
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) && exitErr.ExitCode() == 1 {
		err = exec.Command("podman", "pull", p.tag).Run()
		if err != nil {
			p.logError(err, "couldn't run pull with podman: "+p.tag)
			return nil, nil, err
		} else {
			return nil, nil, fmt.Errorf("podman exited unexpectedly")
		}
	} else if err != nil {
		p.logError(err, "couldn't run image check with podman")
		return nil, nil, err
	}

	// Check if path is set; if so, bind runhook in
	// otherwise, use existing runhook in container
	p.args = append(p.args,
		"run",
		"--preserve-fds=2",
	)
	if p.path != "" {
		// Set this to be an ephemeral container and
		// mount the script as a volume
		p.args = append(p.args, "--rm", "-v")
		if err = p.setTarget(); err != nil {
			return nil, nil, err
		}

		// Mount the file and set the target/script
		if p.target == "sh" && p.script != "" {
			// Runhook case
			p.args = append(p.args,
				fmt.Sprintf("%s:%s:Z", p.path, rundir),
				"-w",
				rundir,
				p.tag,
				"sh",
				filepath.Base(p.script),
			)
			// Reset script so base plugin doesn't append it
			p.script = ""
		} else if p.target != "" {
			// Binary case
			p.args = append(p.args,
				fmt.Sprintf("%s:%s/%s:Z", p.target, rundir, filepath.Base(p.target)),
				"-w",
				rundir,
				p.tag,
				fmt.Sprintf("./%s", filepath.Base(p.target)),
			)
		} else {
			return nil, nil, fmt.Errorf("incorrectly formatted command, target is not sh and script is set")
		}
	} else {
		// Pre-existing runhook case
		p.args = append(p.args, p.tag, "sh", runhook)
	}
	// Overwrite the target to be podman
	p.target = "podman"

	return p.Plugin.Start(ctx)
}
