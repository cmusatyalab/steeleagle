package dsl

import (
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/sdk/geo"
	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/rs/zerolog"
)

// MissionData holds extra data that is useful for DSL tasks.
type MissionData struct {
	Cap      config.DriverCap       // cap corresponding to this device
	Manifest config.MissionManifest // mission manifest corresponding to this mission
	Map      geo.Map                // mission map initialized from GeoJSON (optional)
	Role     params.Role            // role in the current mission
	Log      zerolog.Logger         // logger for this mission
}
