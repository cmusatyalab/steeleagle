package types

import "github.com/cmusatyalab/steeleagle/sdk/dsl"

// GlobalPosition is the DSL version of an SDK GlobalPosition.
type GlobalPosition struct {
	Latitude  float64
	Longitude float64
	Altitude  float32
	Heading   float32
}

// Type implementation
func (*GlobalPosition) Type() {}

// Type assertion
var _ dsl.Datatype = &GlobalPosition{}

// RelativePosition is the DSL version of an SDK RelativePosition.
type RelativePosition struct {
	X     float32
	Y     float32
	Z     float32
	Angle float32
}

// Type implementation
func (*RelativePosition) Type() {}

// Type assertion
var _ dsl.Datatype = &RelativePosition{}

// Velocity is the DSL version of an SDK Velocity.
type Velocity struct {
	XVel       float32
	YVel       float32
	ZVel       float32
	AngularVel float32
}

// Type implementation
func (*Velocity) Type() {}

// Type assertion
var _ dsl.Datatype = &Velocity{}

// Pose is the DSL version of an SDK Pose.
type Pose struct {
	Pitch float32
	Roll  float32
	Yaw   float32
}

// Type implementation
func (*Pose) Type() {}

// Type assertion
var _ dsl.Datatype = &Pose{}

// PoseVelocity is the DSL version of an SDK PoseVelocity.
type PoseVelocity struct {
	PitchVel float32
	RollVel  float32
	YawVel   float32
}

// Type implementation
func (*PoseVelocity) Type() {}

// Type assertion
var _ dsl.Datatype = &PoseVelocity{}
