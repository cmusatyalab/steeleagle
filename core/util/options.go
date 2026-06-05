package util

type PluginOption func(*BasePlugin)

func WithName(name string) PluginOption {
	return func(k *BasePlugin) {
		k.name = name
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

func WithTargetArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.eargs = append(k.eargs, args...)
	}
}

func WithScriptArgs(args []string) PluginOption {
	return func(k *BasePlugin) {
		k.sargs = args
	}
}
