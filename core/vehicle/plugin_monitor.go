package vehicle

import (
	"context"
	"net"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type pluginMonitor struct {
	pluginCfg     PluginConfig
	restartPolicy restartPolicy
	log           zerolog.Logger
	pluginResetCb func(pluginType, string, net.Listener, *grpc.ClientConn)
}

type restartPolicy int

const (
	noRestart = iota
	alwaysRestart
)

type pluginType int

const (
	driverPlugin = iota
	missionPlugin
	otherPlugin
)

const numPluginRestartAttempts = 5

// Monitors each plugin and logs it if it exits unexpectedly. Canceling ctx
// kills plugin subprocesses too, so an exit observed after ctx is done is
// treated as expected and not logged.
func (m *pluginMonitor) start(ctx context.Context) {
	plugins := make(map[pluginType]util.Plugin)
	plugins[driverPlugin] = m.pluginCfg.Driver
	if m.pluginCfg.Mission != nil {
		plugins[missionPlugin] = m.pluginCfg.Mission
	}
	for pluginType, plugin := range plugins {
		go func() {
		PluginLoop:
			for {
				err := plugin.Wait()
				if ctx.Err() != nil {
					return
				}
				m.handleExit(ctx, plugin, pluginType, err)

				switch m.restartPolicy {
				case noRestart:
					break PluginLoop
				default:
				}
			}
		}()
	}
}

// Handle plugin exit based on the configured restart policy.
func (m *pluginMonitor) handleExit(ctx context.Context, p util.Plugin, pluginType pluginType, err error) {
	m.log.Err(err).Str("plugin", p.Name()).Msg("plugin exited unexpectedly")
	switch m.restartPolicy {
	case noRestart:
	case alwaysRestart:
		attempts := 0
		for {
			ln, conn, err := p.Start(ctx)
			if err != nil {
				m.log.Err(err).Str("plugin", p.Name()).Msg("error restarting plugin")
				attempts += 1
				if attempts > numPluginRestartAttempts {
					break
				}
				continue
			}
			m.pluginResetCb(pluginType, p.Name(), ln, conn)
		}
	default:
		m.log.Error().Str("plugin", p.Name()).
			Msg("restart policy unimplemented")
	}
}
