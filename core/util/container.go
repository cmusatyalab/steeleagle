package util

import (
	"fmt"
    "os/exec"
	
    "github.com/rs/zerolog/log"
)

type ContainerPlugin struct {
	Plugin
	tag  string
}

func CreateContainerPlugin(tag string, options ...PluginOption) ContainerPlugin {
	// Create the plugin
    p := ContainerPlugin{
        Plugin: CreatePlugin(options...),
        tag: tag,
    }

	return p
}

func (p *ContainerPlugin) SetTarget() error {
	// Make sure podman is installed
	_, err := exec.LookPath("podman")
	if err != nil {
		log.Error().Err(err).Msg("couldn't find podman, have you installed it?")
		return err
	}

	// Check whether the image exists
	err = exec.Command("podman", "image", "exists", p.tag).Run()
	if err != nil {
		log.Error().Err(err).Msg("couldn't run image check with podman")
		return err
	}
	if exitErr, ok := err.(*exec.ExitError); ok {
		if exitErr.ExitCode() == 1 {
			return fmt.Errorf("container image %s not found", p.tag)
		}
	}

    // Check if path is set; if so, bind runhook in
    // otherwise, use existing runhook in container
    p.target = append(p.target,
        "podman",
        "run",
        "--rm",
        "--preserve-fd=3,4",
    )
    if p.path != "" {
        p.target = append(p.target, "-v")
        if err = p.SetTarget(); err != nil {
            return err
        }
        // Bind the file
        p.target[len(p.target) - 1] = fmt.Sprintf("%s:/%s:Z", p.target[len(p.target) - 1], runhook)
        p.target = append(p.target, p.tag, "sh", fmt.Sprintf("/%s", runhook))
    } else {
        p.target = append(p.target, p.tag, "sh", fmt.Sprintf("/%s", runhook))
    }

    return nil
}
