package buildtools

import (
	"fmt"
	"strings"

	"github.com/cmusatyalab/steeleagle/sdk/geo"
	"github.com/cmusatyalab/steeleagle/sdk/preprocess"
)

// Import paths of the SDK packages the overlay treats specially.
const (
	// sdkPkgPath is the root package of the SDK. Its module is always
	// overlaid, since everything preprocessed builds against it.
	sdkPkgPath = "github.com/cmusatyalab/steeleagle/sdk"
	// paramsPkgPath is the package constants are generated into.
	paramsPkgPath = "github.com/cmusatyalab/steeleagle/sdk/params"
)

// OverlayConfig returns the preprocessing c asks for: the SDK's module
// (whatever module path or version it resolves to) is overlaid, scrubbed
// according to the cap file, and the constants named by the cap file,
// manifest and GeoJSON (see constTypes) are generated into the params
// package. The caller sets where and how the packages are loaded, and any
// other modules to overlay.
func (c *Config) OverlayConfig() (preprocess.OverlayConfig, []*CompileError) {
	cfg := preprocess.OverlayConfig{ModulesOf: []string{sdkPkgPath}}
	if c.Cap != nil {
		cfg.Supports = c.Cap.Supports
	}
	types, errs := c.constTypes()
	if len(errs) > 0 {
		return cfg, errs
	}
	cfg.Consts = map[string]map[string][]string{paramsPkgPath: types}
	return cfg, nil
}

// constTypes returns the constants to generate in the params package, by
// type name, named by the cap file, manifest and GeoJSON: camera names from
// the cap file, roles, squawks and engines (typed by their result message)
// from the manifest, and GeoJSON feature names (typed by their geometry).
// Every engine of the flow must be declared in the manifest. A name may only
// be declared once per type.
func (c *Config) constTypes() (map[string][]string, []*CompileError) {
	types := map[string][]string{}
	var errs []*CompileError
	add := func(typeName, name, what string) {
		for _, n := range types[typeName] {
			if n == name {
				errs = append(errs, &CompileError{Err: fmt.Errorf("%s %q is declared more than once", what, name)})
				return
			}
		}
		types[typeName] = append(types[typeName], name)
	}
	if c.Cap != nil {
		for _, camera := range c.Cap.Cameras {
			add("Camera", camera.Name, "camera")
		}
	}
	// Engine types by name, from the manifest
	engines := map[string]string{}
	if c.Manifest != nil {
		for _, r := range c.Manifest.Info.Roles {
			add("Role", r, "role")
		}
		for _, s := range c.Manifest.Info.Squawks {
			add("Squawk", s, "squawk")
		}
		for _, e := range c.Manifest.Engines {
			typeName := e.Result[strings.LastIndex(e.Result, "/")+1:]
			if typeName == "" {
				errs = append(errs, &CompileError{
					Err: fmt.Errorf("engine %s has malformed result proto message id %q", e.Name, e.Result),
				})
				continue
			}
			if _, ok := engines[e.Name]; ok {
				errs = append(errs, &CompileError{Err: fmt.Errorf("engine %q is declared more than once", e.Name)})
				continue
			}
			// Engines are typed by their result message, e.g. a
			// DetectionResult engine is a params.DetectionEngine
			if base, ok := strings.CutSuffix(typeName, "Result"); ok && base != "" {
				typeName = base + "Engine"
			}
			engines[e.Name] = typeName
			add(typeName, e.Name, "engine")
		}
	}
	if c.Flow != nil {
		for _, e := range c.Flow.Engines {
			if _, ok := engines[e.Name]; !ok {
				errs = append(errs, &CompileError{Err: fmt.Errorf("flow engine %q is not declared in the manifest", e.Name)})
			}
		}
	}
	if c.GeoJson != nil {
		features, err := geo.FeatureNamesFromGeoJson(c.GeoJson)
		if err != nil {
			errs = append(errs, &CompileError{Err: err})
		}
		for typeName, names := range features {
			for _, name := range names {
				add(typeName, name, "GeoJSON feature")
			}
		}
	}
	if len(errs) > 0 {
		return nil, errs
	}
	return types, nil
}
