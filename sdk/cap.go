package sdk

import (
	"bytes"
	"os"
	"strings"

	"github.com/BurntSushi/toml"
)

// servicesRoot is the capability path prefix under which all services live.
const servicesRoot = "steeleagle_protocol/v1/services/"

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
	// Name of the camera ("rgb" e.g.)
	Name string `toml:"name"`
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
	// Whether or not the camera is a primary camera; primary cameras
	// cannot be streamed simultaneously with other primary cameras
	Primary bool `toml:"primary"`
}

// Supported holds the SDK services this vehicle implements. Services are
// opt-in: a service, and every method under it, is unsupported unless
// listed here.
type Supported struct {
	// Services that are supported
	Services []string `toml:"services"`
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
	// Name of the plugin that serves this vehicle ("driver" e.g.)
	Plugin string `toml:"plugin"`
	// Device information
	Device Device `toml:"device"`
	// Camera information
	Cameras []Camera `toml:"cameras"`
	// Supported service information
	Supported Supported `toml:"supported"`
	// Unsupported type information
	Unsupported Unsupported `toml:"unsupported"`
	// Set of all supported services, used for fast queries
	supportedServices map[string]struct{}
	// Merged set of all unsupported types, used for fast queries
	unsupportedSet map[string]struct{}
}

// serviceOf returns the service capability path that name belongs to (e.g.
// "steeleagle_protocol/v1/services/driver/ControlService" for
// "steeleagle_protocol/v1/services/driver/ControlService/Kill"), or false if
// name is not a service or a member of one.
func serviceOf(name string) (string, bool) {
	rest, ok := strings.CutPrefix(name, servicesRoot)
	if !ok {
		return "", false
	}
	parts := strings.SplitN(rest, "/", 3)
	if len(parts) < 2 || !strings.HasSuffix(parts[1], "Service") {
		return "", false
	}
	return servicesRoot + parts[0] + "/" + parts[1], true
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
	c.supportedServices = make(map[string]struct{}, len(c.Supported.Services))
	for _, s := range c.Supported.Services {
		c.supportedServices[s] = struct{}{}
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

// WriteCapToBytes writes a cap file struct to a TOML byte slice.
func WriteCapToBytes(capFile *CapFile) ([]byte, error) {
	var buf bytes.Buffer
	err := toml.NewEncoder(&buf).Encode(capFile)
	if err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// Supports checks if a cap file supports a type name. A service, or a method
// under one, is only supported if the service is listed in supported/services.
// Everything else is supported unless it is listed as unsupported.
func (c *CapFile) Supports(name string) bool {
	if service, ok := serviceOf(name); ok {
		if _, ok := c.supportedServices[service]; !ok {
			return false
		}
	}
	if _, ok := c.unsupportedSet[name]; ok {
		return false
	}
	return true
}
