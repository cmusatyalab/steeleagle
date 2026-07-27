package types

// Pose wraps a common proto Pose.
type Pose struct {
	Pitch float64
	Roll  float64
	Yaw   float64
}

// Velocity wraps a common proto Velocity.
type Velocity struct {
	XVel       float64
	YVel       float64
	ZVel       float64
	AngularVel float64
}

// GlobalPosition wraps a common proto GlobalPosition.
type GlobalPosition struct {
	Latitude  float64
	Longitude float64
	Altitude  float64
	Heading   float64
}

// RelativePosition wraps a common proto RelativePosition.
type RelativePosition struct {
	X     float64
	Y     float64
	Z     float64
	Angle float64
}
