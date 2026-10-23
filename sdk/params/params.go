// Package params declares the SDK's parameter types. Their const values are
// generated at compile time from a mission's manifest file and GeoJSON, to
// prevent string mismatch errors at runtime.
package params

// Camera is generated to hold all the cameras that can be accessed at runtime.
type Camera string

// DetectionEngine is generated to hold all the detection-returning cognitive
// engines that can be accessed at runtime.
type DetectionEngine string

// ClassificationEngine is generated to hold all the classification-returning
// cognitive engines that can be accessed at runtime.
type ClassificationEngine string

// GuidanceEngine is generated to hold all guidance-returning cognitive
// engines that can be accessed at runtime.
type GuidanceEngine string

// PositionEngine is generated to hold all position-returning cognitive engines
// that can be accessed at runtime.
type PositionEngine string

// GenericEngine is generated to hold all generic byte-returning cognitive
// engines that can be accessed at runtime.
type GenericEngine string

// Point is generated to hold all the possible point features that can be
// accessed at runtime.
type Point string

// LineString is generated to hold all the possible line string features that
// can be accessed at runtime.
type LineString string

// MultiLineString is generated to hold all the possible multi line string features
// that can be accessed at runtime.
type MultiLineString string

// Polygon is generated to hold all the possible polygon features that can be
// accessed at runtime.
type Polygon string

// Role is generated to hold all the possible mission roles that can be
// accessed at runtime.
type Role string

// Squawk is generated to hold all the possible mission squawks that can be
// broadcast at runtime.
type Squawk string
