package util

import (
	"fmt"
	"io"

	"github.com/rs/zerolog"
)

type PluginOption func(*BasePlugin)

// WithName assigns a user readable name to the plugin.
func WithName(name string) PluginOption {
	return func(k *BasePlugin) {
		k.name = name
	}
}

// WithoutClient makes the plugin ignore the client connection to the
// subprocess, returning nil in its place after Start is called.
func WithoutClient() PluginOption {
	return func(k *BasePlugin) {
		k.client = false
	}
}

// WithoutListener makes the plugin ignore the listener connection to the
// subprocess, returning nil in its place after Start is called.
func WithoutListener() PluginOption {
	return func(k *BasePlugin) {
		k.listen = false
	}
}

// WithTimeout sets the number of seconds the plugin waits for its server
// socket to become ready.
func WithTimeout(timeout int) PluginOption {
	return func(k *BasePlugin) {
		k.timeout = timeout
	}
}

// WithPath sets the filesystem path to the plugin package directory or script.
func WithPath(path string) PluginOption {
	return func(k *BasePlugin) {
		k.path = path
	}
}

// WithExecutableFiles registers executables that will be resolved via PATH and
// bind-mounted into the plugin's environment.
func WithExecutableFiles(files []string) PluginOption {
	return func(k *BasePlugin) {
		for _, f := range files {
			k.files[f] = 2
		}
	}
}

// WithFiles registers read-write files that will be bind-mounted into the
// plugin's environment.
func WithFiles(files []string) PluginOption {
	return func(k *BasePlugin) {
		for _, f := range files {
			k.files[f] = 1
		}
	}
}

// WithReadOnlyFiles registers read-only files that will be bind-mounted into
// the plugin's environment.
func WithReadOnlyFiles(files []string) PluginOption {
	return func(k *BasePlugin) {
		for _, f := range files {
			k.files[f] = 0
		}
	}
}

// WithAuthCode sets the AuthCode that the plugin's listener will attach to
// every accepted connection.
func WithAuthCode(code AuthCode) PluginOption {
	return func(k *BasePlugin) {
		k.code = code
	}
}

// WithRunner sets the runner binary (e.g. podman, bwrap) used to launch the
// plugin.
func WithRunner(runner string) PluginOption {
	return func(k *BasePlugin) {
		k.runner = runner
	}
}

// WithRunnerArgs appends arguments passed to the runner before the executable.
func WithRunnerArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.rargs = append(k.rargs, args...)
	}
}

// WithExecutable sets the executable (e.g. sh, python3) used to run the plugin
// script.
func WithExecutable(exec string) PluginOption {
	return func(k *BasePlugin) {
		k.exec = exec
	}
}

// WithExecutableArgs appends arguments passed to the executable before the
// script.
func WithExecutableArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.eargs = append(k.eargs, args...)
	}
}

// WithScript sets an explicit path to the plugin script, bypassing automatic
// discovery.
func WithScript(script string) PluginOption {
	return func(k *BasePlugin) {
		k.script = script
	}
}

// WithScriptArgs sets the arguments passed to the plugin script.
func WithScriptArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.sargs = args
	}
}

// WithoutScriptPathValidation skips script path validation which is useful for
// dynamic binding or for containers which may have all components pre-built
// within them.
func WithoutScriptPathValidation() PluginOption {
	return func(k *BasePlugin) {
		k.check = false
	}
}

// WithACL sets the ACL for the plugin, which allows extra PIDs to access a
// listener.
func WithACL(acl *ACL) PluginOption {
	return func(k *BasePlugin) {
		k.acl = acl
	}
}

// WithLogger sets a custom logger object for the plugin.
func WithLogger(logger zerolog.Logger) PluginOption {
	return func(k *BasePlugin) {
		k.log = logger
	}
}

// WithProcessOutputStream sets the output file stream for the delegate process
// output.
func WithProcessOutputStream(out io.Writer) PluginOption {
	return func(k *BasePlugin) {
		k.outStream = out
	}
}

// WithEnvironment sets an environment key-value pair for the plugin.
func WithEnvironment(key, value string) PluginOption {
	return func(k *BasePlugin) {
		k.environ = append(k.environ, fmt.Sprintf("%s=%s", key, value))
	}
}

// WithParent scopes the plugin under a parent directory so the run directory
// is its child.
func WithParentDir(parentDir string) PluginOption {
	return func(k *BasePlugin) {
		k.parentDir = parentDir
	}
}
