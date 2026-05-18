package util

import (
	"fmt"
    "net"
    "context"
    "os"
    "os/exec"
    "time"
    "path/filepath"
	
    "github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type ProcessPlugin struct {
	BasePlugin
	cmd     *exec.Cmd
}

func CreateProcessPlugin(code AuthCode, name, target string) (*ProcessPlugin, error) {
	// Check that the process target exists
	info, err := os.Stat(target)
	if err != nil {
		if os.IsNotExist(err) {
			log.Error().Err(err).Str("name", name).Str("code", string(code)).Msg("couldn't find plugin, have you installed it?")
			return nil, err
		}
		log.Error().Err(err).Str("name", name).Str("code", string(code)).Msg("couldn't stat plugin target")
		return nil, err
	}

	// If the plugin is a directory, then attach the runhook
	if info.IsDir() {
		// Set info and target to the runhook
		target = filepath.Join(target, runhook)
		info, err = os.Stat(target)
		if err != nil {
			log.Error().Err(err).Str("name", name).Str("code", string(code)).Msg("couldn't stat plugin run hook, is it there?")
		}
	}
	// Ensure that the plugin is runnable
	if info.Mode() & 0o111 == 0 {
		return nil, fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", name)
	}

	// Create the plugin
	p := &ProcessPlugin{
		BasePlugin: BasePlugin{
			name:    name,
			target:  target,
			runtime: Process,
			code:    code,
		},
	}

	return p, nil
}

func (p *ProcessPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
    // Get socket files
	ln, c, err := CreateSocketPairFiles()
    if err != nil {
        return nil, nil, err
    }
	
    // Create the command
	p.cmd = exec.CommandContext(ctx, p.target)
    p.cmd.ExtraFiles = []*os.File{c}
	
    // Run the plugin
	if err := p.cmd.Run(); err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't run target for plugin")
		return nil, nil, err
	}

	// Populate the plugin information
	p.start = time.Now().UnixMilli()
	p.running = true

	return CreateEndpoints(p.code, ln, c)
}

func (p *ProcessPlugin) Stop() error {
	return nil
}
