package config

import "strings"

// servicesRoot is the type path prefix under which all services live.
const servicesRoot = "steeleagle_protocol/v1/services/"

type DriverCamera struct {
	// Name of the camera
	Name string `toml:"name"`
	// Type of the camera ("rgb", e.g.)
	Type string `toml:"type"`
	// Description of where the camera is located on the device (optional)
	Description string `toml:"description,omitempty"`
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
	// Average latency of camera frames (optional)
	Latency float32 `toml:"latency,omitempty"`
	// Whether or not the camera is mounted on the primary gimbal
	Gimbal bool `toml:"gimbal"`
	// Whether or not the camera is a primary camera; primary cameras
	// cannot be streamed simultaneously with other primary cameras
	Primary bool `toml:"primary"`
	// Whether or not the camera stream is encodeable; some raw cameras
	// do not output frames that can be encoded
	Encode bool `toml:"encode"`
	// Whether or not the camera is a default stream at startup (optional);
	// the first default primary camera and all default secondary cameras
	// are streamed when the vehicle starts
	Default bool `toml:"default,omitempty"`
}

type DriverSupported struct {
	// Services that are supported
	Services []string `toml:"services"`
}

type DriverUnsupported struct {
	// Methods that are unsupported
	Methods []string `toml:"methods"`
	// Fields that are unsupported
	Fields []string `toml:"fields"`
	// Enums that are unsupported
	Enums []string `toml:"enums"`
}

type DriverCap struct {
	// Type of driver (one of "copter", "legged", "wheeled", "boat")
	Type string `toml:"type"`
	// Driver cameras (optional)
	Cameras []DriverCamera `toml:"cameras"`
	// Supported services
	Supported DriverSupported `toml:"supported"`
	// Unsupported types
	Unsupported DriverUnsupported `toml:"unsupported"`
	// Set of all supported services, used for fast queries
	supportedSet map[string]struct{}
	// Merged set of all unsupported types, used for fast queries
	unsupportedSet map[string]struct{}
}

// serviceOf returns the service type path that name belongs to (e.g.
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

// buildSets populates the supported and unsupported lookup sets from the
// parsed lists.
func (d *DriverCap) buildSets() {
	d.supportedSet = make(map[string]struct{}, len(d.Supported.Services))
	for _, s := range d.Supported.Services {
		d.supportedSet[s] = struct{}{}
	}
	d.unsupportedSet = make(
		map[string]struct{},
		len(d.Unsupported.Methods)+len(d.Unsupported.Fields)+len(d.Unsupported.Enums),
	)
	for _, list := range [][]string{d.Unsupported.Methods, d.Unsupported.Fields, d.Unsupported.Enums} {
		for _, m := range list {
			d.unsupportedSet[m] = struct{}{}
		}
	}
}

// Supports checks if a driver cap supports a type name. Services or methods under a
// services are only supported if the service is listed in supported. Everything else
// is supported unless it is listed in unsupported.
func (d *DriverCap) Supports(name string) bool {
	if d.supportedSet == nil {
		d.buildSets()
	}
	if service, ok := serviceOf(name); ok {
		if _, ok := d.supportedSet[service]; !ok {
			return false
		}
	}
	if _, ok := d.unsupportedSet[name]; ok {
		return false
	}
	return true
}

// HasService checks whether a driver hosts a service name.
func (d *DriverCap) HasService(name string) bool {
	if d.supportedSet == nil {
		d.buildSets()
	}
	_, ok := d.supportedSet[name]
	return ok
}

// DefaultCameras returns the cameras to stream at vehicle startup: the first
// default primary camera, followed by every default secondary camera, in
// config order.
func (d *DriverCap) DefaultCameras() []DriverCamera {
	var cams []DriverCamera
	primary := false
	for _, c := range d.Cameras {
		if !c.Default {
			continue
		}
		if c.Primary {
			if primary {
				continue
			}
			primary = true
			cams = append([]DriverCamera{c}, cams...)
			continue
		}
		cams = append(cams, c)
	}
	return cams
}
