package util

import (
    "context"
	"fmt"
	"os/exec"
    "net"
    "errors"

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
            p.logError(err, "couldn't run pull with podman")
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
		"--rm",
		"--preserve-fds=2",
	)
	if p.path != "" {
		p.args = append(p.args, "-v")
        if err = p.SetTarget(); err != nil {
			return nil, nil, err
		}
		// Bind the file
		p.args = append(p.args,
			fmt.Sprintf("%s:/%s:Z", p.target, runhook),
			p.tag,
			fmt.Sprintf("./%s", runhook),
		)
	} else {
		p.args = append(p.args, p.tag, fmt.Sprintf("./%s", runhook))
	}
	// Overwrite the target to be podman
	p.target = "podman"

	return p.Plugin.Start(ctx)
}
