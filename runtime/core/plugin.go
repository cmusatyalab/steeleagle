package core

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
