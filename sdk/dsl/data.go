package dsl

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/swarm"
	"github.com/cmusatyalab/steeleagle/sdk/geo"
)

// MissionData holds extra data that is useful for DSL tasks.
type MissionData struct {
	Cap  sdk.CapFile // cap corresponding to this device
	Map  geo.Map     // mission map initialized from GeoJSON (optional)
	Role swarm.Role  // role in the current mission
}
