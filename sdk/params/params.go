// Package params declares the SDK's parameter types. Their const values are
// generated at compile time from a mission's manifest file and GeoJSON, to
// prevent string mismatch errors at runtime.
package params

// DetectionResult is generated to hold all the detection-returning cognitive
// flows that can be accessed at runtime.
type DetectionResult string

// ClassificationResult is generated to hold all the classification-returning
// cognitive flows that can be accessed at runtime.
type ClassificationResult string

// GuidanceResult is generated to hold all guidance-returning cognitive
// flows that can be accessed at runtime.
type GuidanceResult string

// PositionResult is generated to hold all position-returning cognitive flows
// that can be accessed at runtime.
type PositionResult string

// GenericResult is generated to hold all generic byte-returning cognitive
// flows that can be accessed at runtime.
type GenericResult string

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
