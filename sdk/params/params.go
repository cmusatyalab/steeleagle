// Package params declares the SDK's parameter types, generated at compile time
// with the const values a mission's manifest file makes available, to prevent
// string mismatch errors at runtime.
package params

// Engine is generated to hold all the possible cognitive engines that
// can be accessed at runtime.
type Engine string

// MapFeature is generated to hold all the possible map features that
// can be accessed at runtime.
type MapFeature string
