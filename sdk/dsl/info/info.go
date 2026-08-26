// Package info declares the DSL's information types, generated at compile time
// with the const values a mission's manifest file makes available, to prevent
// string mismatch errors at runtime.
package info

// Role is generated to hold all the possible mission roles that can be
// accessed at runtime.
type Role string

// Squawk is generated to hold all the possible mission squawks that can be
// broadcast at runtime.
type Squawk string
