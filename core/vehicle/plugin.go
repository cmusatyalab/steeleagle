package vehicle

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
)

type Plugin struct {
    Name string
    Path string
    Runtime PluginRuntime
    Type PluginType
}
