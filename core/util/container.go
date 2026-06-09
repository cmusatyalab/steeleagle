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
	*BasePlugin
	tag string
}

func CreateContainerPlugin(tag string, options ...PluginOption) (*ContainerPlugin, error) {
	// Create the plugin
    internal, err := CreateBasePlugin(options...)
    if err != nil {
        return nil, err
    }
	p := &ContainerPlugin{
		BasePlugin: internal,
		tag:    tag,
	}
    p.runner = "podman"

	return p, nil
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
        // Attempt to pull the container
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

	// Check if path is set; if so, bind runhook in otherwise,
    // use existing runhook in container
    args := []string{
        "run",
        "-e",
        fmt.Sprintf("%s=%s", ClientSockEnv, p.lnSock),
        "-e",
        fmt.Sprintf("%s=%s", ListenSockEnv, p.cSock),
        "-v",
        fmt.Sprintf("%s:%s:Z", p.runDir, p.runDir),
    }
    // Append the existing runner args onto these args,
    // since we want to preserve any passed in args
    p.rargs = append(args, p.rargs...)

    // Check if the container itself is runnable
    runnable, err := isContainerRunnable(p.tag)
    if err != nil {
        return nil, nil, err
    }

    if !runnable {
	    // Set the executable/script
	    if err = p.BasePlugin.findExecutable(); err != nil {
	    	return nil, nil, err
	    }
        // Bind in the right files
        if p.isPkg {
            p.rargs = append(
                p.rargs, "-v",
                fmt.Sprintf("%s:/%s:Z", p.path, bindDir),
            )
        } else if p.path != "" {
            p.rargs = append(
                p.rargs, "-v",
                fmt.Sprintf("%s:/%s/%s:Z", p.path, bindDir, filepath.Base(p.path)),
            )
        } else {
            return nil, nil, fmt.Errorf("podman couldn't find a valid path, runhook, or package")
        }
        p.rargs = append(p.rargs, "-w", "/"+bindDir, p.tag)
        p.script = "./"+filepath.Base(p.script)
    } else {
        p.rargs = append(p.rargs, "-w", "/"+bindDir, p.tag)
        p.exec = "sh"
        p.script = fmt.Sprintf("/%s/%s", bindDir, runHook)
    }
	
    return p.BasePlugin.Start(ctx)
}

func isContainerRunnable(tag string) (bool, error) {
    // Check if a runhook exists in the container
    cmd := exec.Command("podman", "run", "--rm", tag, "test", "-f", fmt.Sprintf("/%s/%s", bindDir, runHook))
    err := cmd.Run()
    if err == nil {
        return true, nil
    }
	var exitErr *exec.ExitError
    if errors.As(err, &exitErr) {
        return false, nil
    } else {
        return false, err
    }
}
