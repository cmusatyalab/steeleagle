package util

import (
    "os/exec"
	
    "github.com/rs/zerolog/log"
)

type SandboxPlugin struct {
	Plugin
}

func CreateSandboxPlugin(options ...PluginOption) SandboxPlugin {
	// Create the plugin
	p := &SandboxPlugin{
        Plugin: CreatePlugin(options...),
	}

	return p
}

func (p *SandboxPlugin) SetTarget() error {
	// Make sure bubblewrap is installed
	_, err := exec.LookPath("bwrap")
	if err != nil {
		log.Error().Err(err).Msg("couldn't find bubblewrap (bwrap), have you installed it?")
		return err
	}

    // Add the correct bubblewrap permissions
    p.target = append(p.target,
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/bin", "/bin",
        "--proc", "/proc",
        "--dev", "/dev",
        "--unshare-all",
        "--share-net",
        "--die-with-parent",
        "--fd", "3", "3",
        "--fd", "4", "4",
    )

    return p.SetTarget()
}
