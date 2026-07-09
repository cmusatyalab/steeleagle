package vehicle

import (
	_ "embed"

	driverpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/core/util"
)

// VideoStreamingType determines the type of video streaming that the vehicle
// uses.  RTSP will forward an existing RTSP stream from the driver. Frames
// will encode individually sent frames into an RTSP stream.
type VideoStreamingType int

const (
	RTSP VideoStreamingType = iota
	Frames
)

// VideoResolution determines the resolution at which the stream is requested
// from the driver, and the resolution that is transmitted if there is
// sufficient bandwidth.
type VideoResolution int

const (
	Res480P VideoResolution = iota
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

func (v VideoResolution) ToProto() driverpb.GetVideoStreamURLRequest_Resolution {
	switch v {
	case Res480P:
		return driverpb.GetVideoStreamURLRequest_RESOLUTION_480P
	case Res720P:
		return driverpb.GetVideoStreamURLRequest_RESOLUTION_720P
	case Res1080P:
		return driverpb.GetVideoStreamURLRequest_RESOLUTION_1080P
	case Res4K:
		return driverpb.GetVideoStreamURLRequest_RESOLUTION_4K
	default:
		return driverpb.GetVideoStreamURLRequest_RESOLUTION_720P
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
