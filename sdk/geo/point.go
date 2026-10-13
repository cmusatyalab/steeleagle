package geo

// GeoPoint is a global position used in returns from map methods. This is
// functionally identical to dsl/datatypes.GlobalPosition but does not rely
// on it to prevent import cycles. By design, all SDK modules are
// hierarchically above the DSL and thus no SDK module should import
// DSL datatypes/actions/events.
type GeoPoint struct {
	Latitude  float64
	Longitude float64
	Altitude  float32
	Heading   float32
}
