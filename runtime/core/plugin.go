package core

import (
    "context"
)

type PluginRuntime int

const (
    Process PluginRuntime = iota
    Container
    Sandbox
)

type PluginType int

const (
    Control PluginType = iota
    Mission
    Engine
    UserInterface
    Logger
)

type Plugin struct {
    Name string
    Path string
    Runtime PluginRuntime
    Type PluginType
}

type PluginOption func(*Plugin)

func createPlugin(options ...PluginOption) (*Plugin, error) {
    return nil, nil
}

func (i *Plugin) start(ctx context.Context, workDir string) error {
    return nil
}
