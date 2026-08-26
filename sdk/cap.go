package sdk

import (
	"os"

	"github.com/BurntSushi/toml"
)

// Device holds information about the vehicle.
type Device struct {
	// Model name of the device
	Model string `toml:"model"`
	// Manufacturer name of the device
	Manufacturer string `toml:"manufacturer"`
	// Type of the device ("copter" e.g.)
	Type string `toml:"type"`
}

// Camera holds information about a vehicle camera.
type Camera struct {
	// Type of the camera ("rgb" e.g.)
	Type string `toml:"type"`
	// Horizontal resolution of the camera
	HRes uint32 `toml:"hres"`
	// Vertical resolution of the camera
	VRes uint32 `toml:"vres"`
	// Horizontal FOV of the camera
	HFov uint32 `toml:"hfov"`
	// Vertical FOV of the camera
	VFov uint32 `toml:"vfov"`
	// Maximum FPS of the camera
	Fps uint32 `toml:"fps"`
	// Average latency of camera frames
	Latency float32 `toml:"latency"`
	// Whether or not the camera is mounted on the primary gimbal
	Gimbal bool `toml:"gimbal"`
}

// Unsupported holds all the unsupported SDK types for this vehicle.
type Unsupported struct {
	// Methods that are unsupported
	Methods []string `toml:"methods"`
	// Fields that are unsupported
	Fields []string `toml:"fields"`
	// Enums that are unsupported
	Enums []string `toml:"enums"`
}

// CapFile stores data about the static parameters of a vehicle and
// which methods, fields, and enums from the SDK that it supports.
// Can be used to scrub the SDK and create a compiler overlay that omits
// unsupported types.
type CapFile struct {
	// Device information
	Device Device `toml:"device"`
	// Camera information
	Cameras []Camera `toml:"cameras"`
	// Unsupported type information
	Unsupported Unsupported `toml:"unsupported"`
	// Merged set of all unsupported types, used for fast queries
	unsupportedSet map[string]struct{}
}

// ParseCapFromBytes parses a cap file from a TOML byte slice.
func ParseCapFromBytes(content []byte) (*CapFile, error) {
	c := &CapFile{}
	err := toml.Unmarshal(content, c)
	if err != nil {
		return nil, err
	}
	// Create an unsupported set that holds all unsupported types
	// for easy lookup later
	merged := make(
		[]string, 0,
		len(c.Unsupported.Methods)+len(c.Unsupported.Fields)+len(c.Unsupported.Enums),
	)
	merged = append(merged, c.Unsupported.Methods...)
	merged = append(merged, c.Unsupported.Fields...)
	merged = append(merged, c.Unsupported.Enums...)
	c.unsupportedSet = make(map[string]struct{}, len(merged))
	for _, m := range merged {
		c.unsupportedSet[m] = struct{}{}
	}
	return c, nil
}

// ParseCapFromFile parses a cap file from a filepath.
func ParseCapFromFile(filepath string) (*CapFile, error) {
	content, err := os.ReadFile(filepath)
	if err != nil {
		return nil, err
	}
	return ParseCapFromBytes(content)
}

// Supports checks if a cap file supports a type name.
func (c *CapFile) Supports(name string) bool {
	if _, ok := c.unsupportedSet[name]; ok {
		return false
	}
	return true
}
