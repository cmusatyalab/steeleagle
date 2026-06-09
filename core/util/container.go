package util

import (
    "os"
    "time"
    "strings"
	"context"
	"errors"
	"fmt"
	"net"
    "strconv"
	"os/exec"
	"path/filepath"

	"google.golang.org/grpc"
)

type ContainerPlugin struct {
	*BasePlugin
	tag string
    cid string
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

    // Create a cid file to capture the container ID
    // which is needed to get the container PID
    cidFile := filepath.Join(p.runDir, ".cid")
    p.rargs = append(p.rargs, "--cidfile", cidFile)

    if !runnable {
	    // Set the executable/script
	    if err = p.BasePlugin.findExecutable(); err != nil {
	    	return nil, nil, err
	    }
        // Bind in the right files
        if p.pkg {
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
	
    // Append the podman PID namespace to the allowed PIDs
    ln, conn, err := p.BasePlugin.Start(ctx)
    if err != nil {
        return nil, nil, err
    }
    err = p.setCID(cidFile)
    if err != nil {
        return nil, nil, err
    }
    pid, err := p.getPID()
    cl, ok := ln.(*codedListener)
    if ok {
        cl.acl.pids = append(cl.acl.pids, pid)
    }
    return ln, conn, err
}

func (p *ContainerPlugin) setCID(cidPath string) error {
    // Retry reads to give container time to write to cid file
    deadline := time.Now().Add(time.Duration(p.timeout) * time.Second)
    for time.Now().Before(deadline) {
        data, err := os.ReadFile(cidPath)
        if err == nil && len(strings.TrimSpace(string(data))) > 0 {
            p.cid = strings.TrimSpace(string(data))
            return nil
        }
        time.Sleep(50 * time.Millisecond)
    }
    return fmt.Errorf("timed out waiting for container ID file: %s", cidPath)
}

func (p *ContainerPlugin) getPID() (int, error) {
    out, err := exec.Command("podman", "inspect", "--format", "{{.State.Pid}}", p.cid).Output()
    if err != nil {
        return -1, fmt.Errorf("couldn't inspect container %s: %w", p.cid, err)
    }
    pid, err := strconv.Atoi(strings.TrimSpace(string(out)))
    if err != nil {
        return -1, fmt.Errorf("couldn't parse container pid: %w", err)
    }
    return pid, nil
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
