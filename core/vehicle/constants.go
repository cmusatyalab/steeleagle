package vehicle

import (
	_ "embed"

	"github.com/cmusatyalab/steeleagle/core/util"
)

// VideoStreamType determines the type of video streaming that the vehicle
// uses. RTSP will forward an existing RTSP stream from the driver. Frames will
// encode individually sent frames into an RTSP stream.
type VideoStreamType int

const (
	RTSP VideoStreamType = iota
	Frames
)

// VideoResolution determines the resolution at which the stream is requested
// from the driver, and the resolution that is transmitted if there is
// sufficient bandwidth.
type VideoResolution int

const (
	ResUnknown VideoResolution = iota
	Res480P
	Res720P
	Res1080P
	Res4K
)

// Converts VideoResolution to an int pair representation.
func (v VideoResolution) Ints() (int, int) {
	switch v {
	case Res480P:
		return 854, 480
	case Res720P:
		return 1280, 720
	case Res1080P:
		return 1920, 1080
	case Res4K:
		return 3840, 2160
	default:
		return 1280, 720
	}
}

// DefaultPort is the port to use if no port is specified.
const DefaultPort int = 50000

// MainSocketName is the name for the main services socket.
const MainSocketName string = "main"

// AdminSocketName is the name for the admin services socket.
const AdminSocketName string = "admin"

// MainListenerName is the listener name for the main listener displayed in
// logs.
const MainListenerName string = "main"

// AdminListenerName is the listener name for the admin listener displayed in
// logs.
const AdminListenerName string = "admin"

// MissionListenerName is the listener name for the mission listener displayed
// in logs.
const MissionListenerName string = "mission"

// ServerListenerName is the listener name for the server listener displayed in
// logs.
const ServerListenerName string = "server"

// ReservedNames is a slice of reserved listener names.
var ReservedNames = []string{MainListenerName, AdminListenerName, MissionListenerName, ServerListenerName}

// ReservedCodes is a slice of reserved listener codes.
var ReservedCodes = []util.AuthCode{util.AdminCode, util.MissionCode, util.ServerCode}

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law is provided.

//go:embed defaults/check.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.
