package util

import (
	"fmt"
    "net"
    "context"
    "os"
    "os/exec"
    "strings"
    "time"
	
    "github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type ContainerPlugin struct {
	BasePlugin
	cid string
	tag string
	cmd *exec.Cmd
}

func CreateContainerPlugin(code AuthCode, name, target, tag string) (*ContainerPlugin, error) {
	// Make sure podman is installed
	_, err := exec.LookPath("podman")
	if err != nil {
		log.Error().Err(err).Msg("couldn't find podman, have you installed it?")
		return nil, err
	}

	// Check whether the image exists
	err = exec.Command("podman", "image", "exists", tag).Run()
	if err != nil {
		log.Error().Err(err).Msg("couldn't run image check with podman")
		return nil, err
	}
	if exitErr, ok := err.(*exec.ExitError); ok {
		if exitErr.ExitCode() == 1 {
			return nil, fmt.Errorf("container image %s not found", tag)
		}
	}

	// Create the command and plugin
	p := &ContainerPlugin{
		BasePlugin: BasePlugin{
			name:    name,
			runtime: Container,
			code:    code,
		},
		tag: tag,
	}

	return p, nil
}

func (p *ContainerPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Write container id to a temporary file so it can be read
	cidFile, _ := os.CreateTemp("", "cid-*")
	cidFile.Close()
	defer os.Remove(cidFile.Name())

	// Get socket files
	ln, c, err := CreateSocketPairFiles()
    if err != nil {
        return nil, nil, err
    }
	
    // Create the command
	p.cmd = exec.CommandContext(ctx, "podman", "run", "--rm",
		"--cidfile", cidFile.Name(),
		"--preserve-fd", "3",
		p.tag)
    p.cmd.ExtraFiles = []*os.File{c}

	// Run target
	if err := p.cmd.Run(); err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't run target for plugin")
		return nil, nil, err
	}

	// Get container id from the temporary file
	data, _ := os.ReadFile(cidFile.Name())
	p.cid = strings.TrimSpace(string(data))
	p.start = time.Now().UnixMilli()
	p.running = true

	return CreateEndpoints(p.code, ln, c)
}

func (p *ContainerPlugin) isRunning() (bool, error) {
	out, err := exec.Command("podman", "inspect",
		"--format", "{{.State.Running}}",
		p.cid,
	).Output()
	if err != nil {
		return false, err
	}
	return strings.TrimSpace(string(out)) == "true", nil
}

func (p *ContainerPlugin) Stop() error {
	if err := exec.Command("podman", "stop", p.cid).Run(); err != nil {
		return err
	}
	return p.cmd.Wait()
}
