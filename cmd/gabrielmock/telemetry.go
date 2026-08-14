package main

import (
	"math"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Base position the synthetic vehicle drifts around (Carnegie Mellon University).
const (
	baseLatitude  = 40.4433
	baseLongitude = -79.9436
	orbitRadius   = 0.0005 // degrees, roughly 50m
	degPerTick    = 6.0    // one full orbit every 60 ticks
)

func ptr[T any](v T) *T { return &v }

// syntheticTelemetry builds a plausible Telemetry message for tick seq. The
// vehicle orbits a fixed point and its battery drains and resets on a
// sawtooth, purely to give the stream some visible variation over time.
func syntheticTelemetry(seq uint64) *telemetrypb.Telemetry {
	angle := float64(seq) * degPerTick * math.Pi / 180
	lat := baseLatitude + orbitRadius*math.Sin(angle)
	lon := baseLongitude + orbitRadius*math.Cos(angle)
	heading := float32(math.Mod(float64(seq)*degPerTick, 360))
	battery := uint32(100 - (seq/20)%40)

	return telemetrypb.Telemetry_builder{
		Timestamp:   timestamppb.Now(),
		BatteryInfo: telemetrypb.BatteryInfo_builder{Percentage: ptr(battery)}.Build(),
		GpsInfo:     telemetrypb.GpsInfo_builder{Satellites: ptr(uint32(12))}.Build(),
		PositionInfo: telemetrypb.PositionInfo_builder{
			GlobalPosition: commonpb.GlobalPosition_builder{
				Latitude:  ptr(lat),
				Longitude: ptr(lon),
				Altitude:  ptr(float32(30.0)),
				Heading:   ptr(heading),
			}.Build(),
		}.Build(),
		GimbalInfo: telemetrypb.GimbalInfo_builder{
			PoseBody: commonpb.Pose_builder{Pitch: ptr(float32(-45.0))}.Build(),
		}.Build(),
	}.Build()
}
