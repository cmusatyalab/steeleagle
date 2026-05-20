package util

import (
	"fmt"
    "net"
    "context"
    "os"
    "os/exec"
    "time"
    "path/filepath"
	
	"github.com/google/uuid"
    "github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type Plugin struct {
	name    string
	path    string
    target  []string
	start   int64 // plugin start time
	running bool
	code    AuthCode
	cmd     *exec.Cmd
}

func CreatePlugin(options ...PluginOption) Plugin {
    // Set default input options and retrieve options
    plugin := Plugin{
        name: uuid.New().String(),
        code: UnknownCode,
    }
	for _, option := range options {
		option(&plugin)
	}

	return plugin
}

func (p *Plugin) SetTarget() error {
    info, err := os.Stat(p.path)
    if err != nil {
    	if os.IsNotExist(err) {
    		log.Error().Err(err).Str("name", p.name).Str("code", string(p.code)).Msg("couldn't find plugin, have you installed it?")
    		return err
    	}
    	log.Error().Err(err).Str("name", p.name).Str("code", string(p.code)).Msg("couldn't stat plugin path")
    	return err
    }
    
    // If the plugin is a directory, then use the runhook as the
    // target executable
    var target string
    if info.IsDir() {
    	// Set info and target to the runhook
    	target = filepath.Join(p.path, runhook)
    	info, err = os.Stat(target)
    	if err != nil {
    		log.Error().Err(err).Str("name", p.name).Str("code", string(p.code)).Msg("couldn't stat plugin run hook, is it there?")
            return err
    	}
    }
    // Ensure that the target is runnable
    if info.Mode() & 0o111 == 0 {
    	return fmt.Errorf("plugin %s is not executable nor does it contain an executable runhook", p.name)
    }

    // Assign target
    p.target = append(p.target, target)

    return nil
}

func (p *Plugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
    // Get socket files
	ln, c, err := CreateSocketPairFiles()
    if err != nil {
        return nil, nil, err
    }
	
    // Create the command
	p.cmd = exec.CommandContext(ctx, p.target)
    p.cmd.ExtraFiles = []*os.File{c, ln}
	
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

func (p *Plugin) Name() string {
	return p.name
}

func (p *Plugin) Stop() error {
	return p.cmd.Process.Kill()
}
