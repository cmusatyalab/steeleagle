package vehicle

import (
	_ "embed"
	"time"
)

//go:embed defaults/laws.toml
var DefaultLaw []byte // DefaultLaw is the default control law if no user-specified law is provided.

// Socket path for main services
const (
	MainSocketName = "main"
)

// Name of the plugin that runs the loaded mission
const MissionPluginName = "mission"

// Default name of the local compute service, matching the daemon's default
// hostname.
const DefaultLcsName = "eagled"

// Uriel producer the driver publishes telemetry on, as {vehicle name}.{name};
// Uriel names can't contain '/'. Cameras are published as {vehicle name}.{camera
// name} likewise.
const TelemetryProducerName = "telemetry"

// Driver methods the vehicle calls to start streams, and how long it waits
// for them. Their service is internal to the vehicle, so it is never routed
// to, even if the driver supports it.
const (
	StreamService         = "steeleagle_protocol/v1/services/driver/StreamService"
	StreamCamerasMethod   = "steeleagle_protocol/v1/services/driver/StreamService/StreamCameras"
	StreamTelemetryMethod = "steeleagle_protocol/v1/services/driver/StreamService/StreamTelemetry"
	StreamTimeout         = 10 * time.Second
)

// Locations of engines in a dataflow: served by the local compute service, or
// by the remote one.
const (
	LocalLocation  = "local"
	RemoteLocation = "remote"
)

// Result types of engines, as their plugin tomls name them, that are stored as
// their own type in a ComputeResult; results of any other type are stored as
// generic results.
const (
	DetectionResultType      = "steeleagle_protocol/v1/messages/result/DetectionResult"
	ClassificationResultType = "steeleagle_protocol/v1/messages/result/ClassificationResult"
	GuidanceResultType       = "steeleagle_protocol/v1/messages/result/GuidanceResult"
	PositionResultType       = "steeleagle_protocol/v1/messages/result/PositionResult"
	GenericResultType        = "steeleagle_protocol/v1/messages/result/GenericResult"
)

// Data database file, kept in the vehicle's persistent data directory, and its
// buckets; results are kept in a bucket per engine, named after the engine.
const (
	DataDbName      = "data.db"
	TelemetryBucket = "telemetry"
)
