package plugin

import (
	"fmt"
	"io"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/rs/zerolog"
)

type PluginOption func(*BasePlugin)

// WithName assigns a user readable name to the plugin.
func WithName(name string) PluginOption {
	return func(p *BasePlugin) {
		p.name = name
	}
}

// WithoutClient makes the plugin ignore the client connection to the
// subprocess, returning nil in its place after Start is called.
func WithoutClient() PluginOption {
	return func(p *BasePlugin) {
		p.client = false
	}
}

// WithoutListener makes the plugin ignore the listener connection to the
// subprocess, returning nil in its place after Start is called.
func WithoutListener() PluginOption {
	return func(p *BasePlugin) {
		p.listen = false
	}
}

// WithTimeout sets the number of seconds the plugin waits for its server
// socket to become ready.
func WithTimeout(timeout int) PluginOption {
	return func(p *BasePlugin) {
		p.timeout = timeout
	}
}

// WithPath sets the filesystem path to the plugin package directory or script.
func WithPath(path string) PluginOption {
	return func(p *BasePlugin) {
		p.path = path
	}
}

// WithExecutableFiles registers executables that will be resolved via PATH and
// bind-mounted into the plugin's environment.
func WithExecutableFiles(files []string) PluginOption {
	return func(p *BasePlugin) {
		for _, f := range files {
			p.files[f] = 2
		}
	}
}

// WithFiles registers read-write files that will be bind-mounted into the
// plugin's environment.
func WithFiles(files []string) PluginOption {
	return func(p *BasePlugin) {
		for _, f := range files {
			p.files[f] = 1
		}
	}
}

// WithReadOnlyFiles registers read-only files that will be bind-mounted into
// the plugin's environment.
func WithReadOnlyFiles(files []string) PluginOption {
	return func(p *BasePlugin) {
		for _, f := range files {
			p.files[f] = 0
		}
	}
}

// WithAuthCode sets the AuthCode that the plugin's listener will attach to
// every accepted connection.
func WithAuthCode(code listener.AuthCode) PluginOption {
	return func(p *BasePlugin) {
		p.code = code
	}
}

// WithRunner sets the runner binary (e.g. podman, bwrap) used to launch the
// plugin.
func WithRunner(runner string) PluginOption {
	return func(p *BasePlugin) {
		p.runner = runner
	}
}

// WithRunnerArgs appends arguments passed to the runner before the executable.
func WithRunnerArgs(args []string) PluginOption {
	return func(p *BasePlugin) {
		p.rargs = append(p.rargs, args...)
	}
}

// WithExecutable sets the executable (e.g. sh, python3) used to run the plugin
// script.
func WithExecutable(exec string) PluginOption {
	return func(p *BasePlugin) {
		p.exec = exec
	}
}

// WithExecutableArgs appends arguments passed to the executable before the
// script.
func WithExecutableArgs(args []string) PluginOption {
	return func(p *BasePlugin) {
		p.eargs = append(p.eargs, args...)
	}
}

// WithScript sets an explicit path to the plugin script, bypassing automatic
// discovery.
func WithScript(script string) PluginOption {
	return func(p *BasePlugin) {
		p.script = script
	}
}

// WithScriptArgs sets the arguments passed to the plugin script.
func WithScriptArgs(args []string) PluginOption {
	return func(p *BasePlugin) {
		p.sargs = args
	}
}

// WithoutScriptPathValidation skips script path validation which is useful for
// dynamic binding or for containers which may have all components pre-built
// within them.
func WithoutScriptPathValidation() PluginOption {
	return func(p *BasePlugin) {
		p.check = false
	}
}

// WithAcl sets the ACL for the plugin, which allows extra PIDs to access a
// listener with their own AuthCodes. The plugin's own PID is added to it with
// the plugin's AuthCode when it starts.
func WithAcl(acl *listener.Acl) PluginOption {
	return func(p *BasePlugin) {
		p.acl = acl
	}
}

// WithLogger sets a custom logger object for the plugin.
func WithLogger(logger zerolog.Logger) PluginOption {
	return func(p *BasePlugin) {
		p.log = logger
	}
}

// WithProcessOutputStream sets the output file stream for the delegate process
// output.
func WithProcessOutputStream(out io.Writer) PluginOption {
	return func(p *BasePlugin) {
		p.outStream = out
	}
}

// WithEnvironment adds an environment key-value pair for the plugin.
func WithEnvironment(key, value string) PluginOption {
	return func(p *BasePlugin) {
		p.environ = append(p.environ, fmt.Sprintf("%s=%s", key, value))
		p.envVars = append(p.envVars, key)
	}
}

// WithParentDir sets the directory the plugin's run directory (named after the
// plugin) is created under. If unset, the working directory is used.
func WithParentDir(parentDir string) PluginOption {
	return func(p *BasePlugin) {
		p.parentDir = parentDir
	}
}
