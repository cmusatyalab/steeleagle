package params

// AsString is a string conversion function used to convert params into
// their string name. It is also generated alongside the other enums.
type AsString[T any] func(param T) string

// Engine is generated to hold all the possible cognitive engines that
// can be accessed at runtime.
type Engine int32

// Placemark is generated to hold all the possible GeoJSON placemarks that
// can be accessed at runtime.
type Placemark int32

// Role is generated to hold all the possible mission roles that can be
// accessed at runtime.
type Role int32
