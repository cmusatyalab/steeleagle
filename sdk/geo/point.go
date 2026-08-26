package geo

// GeoPoint is a global position used in returns from map methods. This is
// functionally identical to the dsl/types/GlobalPosition but does not rely
// on it to prevent import cycles. By design, all SDK modules are
// heirarchically above the DSL and thus no SDK module should import
// DSL types/actions/events.
type GeoPoint struct {
	Latitude  float64
	Longitude float64
	Altitude  float32
	Heading   float32
}
