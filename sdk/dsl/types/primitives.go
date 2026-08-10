package types

// GlobalPosition is the DSL version of an SDK GlobalPosition.
type GlobalPosition struct {
	Latitude  float64
	Longitude float64
	Altitude  float32
	Heading   float32
}

// RelativePosition is the DSL version of an SDK RelativePosition.
type RelativePosition struct {
	X     float32
	Y     float32
	Z     float32
	Angle float32
}

// Velocity is the DSL version of an SDK Velocity.
type Velocity struct {
	XVel       float32
	YVel       float32
	ZVel       float32
	AngularVel float32
}

// Pose is the DSL version of an SDK Pose.
type Pose struct {
	Pitch float32
	Roll  float32
	Yaw   float32
}

// PoseVelocity is the DSL version of an SDK PoseVelocity.
type PoseVelocity struct {
	PitchVel float32
	RollVel  float32
	YawVel   float32
}
