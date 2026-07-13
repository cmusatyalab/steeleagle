package vehicle

import (
	"context"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
)

type pluginMonitor struct {
	pluginCfg     PluginConfig
	restartPolicy restartPolicy
	log           zerolog.Logger
}

type restartPolicy int

const (
	noRestart = iota
	alwaysRestart
	onFailure
)

// Monitors each plugin and logs it if it exits unexpectedly. Canceling ctx
// kills plugin subprocesses too, so an exit observed after ctx is done is
// treated as expected and not logged.
func (m *pluginMonitor) start(ctx context.Context) {
	plugins := make([]util.Plugin, 0, 2+len(m.pluginCfg.Plugins))
	plugins = append(plugins, m.pluginCfg.Driver)
	if m.pluginCfg.Mission != nil {
		plugins = append(plugins, m.pluginCfg.Mission)
	}
	plugins = append(plugins, m.pluginCfg.Plugins...)
	for _, plugin := range plugins {
		go func() {
			err := plugin.Wait()
			if ctx.Err() != nil {
				return
			}
			m.handleExit(plugin, err)
		}()
	}
}

// Handle plugin exit based on the configured restart policy.
func (m *pluginMonitor) handleExit(p util.Plugin, err error) {
	switch m.restartPolicy {
	case noRestart:
		m.log.Err(err).Msg("plugin exited unexpectedly")
	default:
		m.log.Error().Str("plugin", p.Name()).
			Msg("restart policy unimplemented")
	}
}
