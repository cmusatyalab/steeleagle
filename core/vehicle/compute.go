package vehicle

import (
	"sync"

	"github.com/cmusatyalab/steeleagle/config"
)

// EngineInfo is info about a particular engine.
type EngineInfo struct {
	Config *config.PluginConfig // engine config
	Local  bool                 // whether or not the engine is local
}

// EngineMap is a map of all available engines.
type EngineMap map[string]*EngineInfo

// flowInfo holds flow info for the vehicle's current dataflow.
type flowInfo struct {
	name string             // current flow name
	spec []byte             // current flow spec in bytes
	flow *config.FlowConfig // current flow config
	mu   sync.Mutex         // mutex
}

// streamInfo holds info on the names for all producer streams.
type streamInfo struct {
	telemetry string   // telemetry producer name
	cameras   []string // camera producer names
}
