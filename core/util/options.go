package util

type PluginOption func(*Plugin)

func WithName(name string) PluginOption {
	return func(k *Plugin) {
		k.name = name
	}
}

func WithPath(path string) PluginOption {
	return func(k *Plugin) {
		k.path = path
	}
}

func WithAuthCode(code AuthCode) PluginOption {
	return func(k *Plugin) {
		k.code = code
	}
}

func WithTargetArgs(args []string) PluginOption {
    return func(k *Plugin) {
        k.args = append(k.args, args...)
    }
}

func WithScriptArgs(args []string) PluginOption {
    return func(k *Plugin) {
        k.sargs = args
    }
}

func WithNamedSockets() PluginOption {
    return func(k *Plugin) {
        k.use_uds = true
    }
}
