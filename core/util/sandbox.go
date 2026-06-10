package util

import (
    "os"
	"context"
	"fmt"
	"net"
	"os/exec"
	"path/filepath"

	"google.golang.org/grpc"
)

type SandboxPlugin struct {
	*BasePlugin
}

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

	return p, nil
}

func (p *SandboxPlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Make sure bubblewrap is installed
	_, err := exec.LookPath("bwrap")
	if err != nil {
		p.logError(err, "couldn't find bubblewrap (bwrap), have you installed it?")
		return nil, nil, err
	}

    // Make sure bubblerap has the right permissions
    err = checkBwrapPermissions()
    if err != nil {
        p.logError(err, "bubblewrap couldn't run")
        return nil, nil, err
    }

	// Add the correct bubblewrap args
    args := []string{
        "--unshare-all",
        "--share-net",
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
        if w == 2 { // executable
            path, err := exec.LookPath(f)
            if err != nil {
                p.logError(err, "couldn't find executable file")
                return nil, nil, err
            }
            args = append(args,
                "--ro-bind",
                path, path,
            )
        } else { // normal file
            _, err := os.Stat(f) // ensure the file exists
            if err != nil {
                p.logError(err, "couldn't stat linked file")
                return nil, nil, err
            }
            path, err := filepath.Abs(f)
            if err != nil {
                p.logError(err, "couldn't get absolute filepath")
                return nil, nil, err
            }
            if w == 1 { // read-write
                args = append(args,
                    "--bind",
                    path, path,
                )
            } else { // read-only
                args = append(args,
                    "--ro-bind",
                    path, path,
                )
            }
        }
    }
    
    // Append the existing runner args onto these args,
    // since we want to preserve any passed in args
    p.rargs = append(args, p.rargs...)

	// Set the executable/script
	if err = p.BasePlugin.findExecutable(); err != nil {
		return nil, nil, err
	}

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
            p.path,
            fmt.Sprintf("/%s/%s", bindDir, filepath.Base(p.path)),
            "--chdir",
            bindDir,
        )
    }
    p.script = fmt.Sprintf("./%s", filepath.Base(p.script))

	return p.BasePlugin.Start(ctx)
}

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
