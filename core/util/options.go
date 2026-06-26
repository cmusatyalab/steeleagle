package util

type PluginOption func(*BasePlugin)

// WithoutServer disables the plugin's server-side socket, making it a fire-and-forget subprocess.
func WithoutServer() PluginOption {
	return func(k *BasePlugin) {
		k.server = false
	}
}

// WithTimeout sets the number of seconds the plugin waits for its server socket to become ready.
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

// WithExecutableFiles registers executables that will be resolved via PATH and bind-mounted into the plugin's environment.
func WithExecutableFiles(files []string) PluginOption {
	return func(k *BasePlugin) {
		for _, f := range files {
			k.files[f] = 2
		}
	}
}

// WithFiles registers read-write files that will be bind-mounted into the plugin's environment.
func WithFiles(files []string) PluginOption {
	return func(k *BasePlugin) {
		for _, f := range files {
			k.files[f] = 1
		}
	}
}

// WithReadOnlyFiles registers read-only files that will be bind-mounted into the plugin's environment.
func WithReadOnlyFiles(files []string) PluginOption {
	return func(k *BasePlugin) {
		for _, f := range files {
			k.files[f] = 0
		}
	}
}

// WithAuthCode sets the AuthCode that the plugin's listener will attach to every accepted connection.
func WithAuthCode(code AuthCode) PluginOption {
	return func(k *BasePlugin) {
		k.code = code
	}
}

// WithRunner sets the runner binary (e.g. podman, bwrap) used to launch the plugin.
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

// WithExecutable sets the executable (e.g. sh, python3) used to run the plugin script.
func WithExecutable(exec string) PluginOption {
	return func(k *BasePlugin) {
		k.exec = exec
	}
}

// WithExecutableArgs appends arguments passed to the executable before the script.
func WithExecutableArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.eargs = append(k.eargs, args...)
	}
}

// WithScript sets an explicit path to the plugin script, bypassing automatic discovery.
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

// WithoutCheck skips script path validation which is useful for dynamic binding or for
// containers which may have all components pre-built within them.
func WithoutCheck() PluginOption {
	return func(k *BasePlugin) {
		k.check = false
	}
}

// WithACL sets the ACL for the plugin, which allows extra PIDs to access a listener.
func WithACL(acl *ACL) PluginOption {
    return func(k *BasePlugin) {
        k.acl = acl
    }
}
