package util

type PluginOption func(*BasePlugin)

func WithoutServer() PluginOption {
    return func(k *BasePlugin) {
        k.server = false
    }
}

func WithTimeout(timeout int) PluginOption {
    return func(k *BasePlugin) {
        k.timeout = timeout
    }
}

func WithPath(path string) PluginOption {
	return func(k *BasePlugin) {
		k.path = path
	}
}

func WithAuthCode(code AuthCode) PluginOption {
	return func(k *BasePlugin) {
		k.code = code
	}
}

func WithRunner(runner string) PluginOption {
    return func(k *BasePlugin) {
        k.runner = runner
    }
}

func WithRunnerArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.rargs = append(k.rargs, args...)
	}
}

func WithExecutable(exec string) PluginOption {
    return func(k *BasePlugin) {
        k.exec = exec
    }
}

func WithExecutableArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.eargs = append(k.eargs, args...)
	}
}

func WithScript(script string) PluginOption {
    return func(k *BasePlugin) {
        k.script = script
    }
}

func WithScriptArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.sargs = args
	}
}
