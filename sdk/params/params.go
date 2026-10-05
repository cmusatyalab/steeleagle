// Package params declares the SDK's parameter types, generated at compile time
// with the const values a mission's manifest file makes available, to prevent
// string mismatch errors at runtime.
package params

// RoIEngine is generated to hold all the RoI-returning cognitive engines
// that can be accessed at runtime.
type RoIEngine string

// ClassifierEngine is generated to hold all the classification-returning
// cognitive engines that can be accessed at runtime.
type ClassifierEngine string

// GuidanceEngine is generated to hold all guidance-returning cognitive
// engines that can be accesseeed at runtime.
type GuidanceEngine string

// JsonEngine is generated to hold all JSON-returning cognitive engines
// that can be accesseeed at runtime.
type JsonEngine string

// GenericEngine is generated to hold all generic byte-returning cognitive
// engines that can be accesseeed at runtime.
type GenericEngine string

// MapFeature is generated to hold all the possible map features that
// can be accessed at runtime.
type MapFeature string
