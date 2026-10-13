package buildtools

import "github.com/cmusatyalab/steeleagle/sdk"

// Options are the options for building against the SDK, shared by SDK
// builds and DSL mission compiles.
type Options struct {
	CapToml      []byte
	ManifestToml []byte
	GeoJson      []byte
	OutputFile   string
}

type Option func(*Options)

// WithCap sets the cap file (as TOML bytes) the SDK is scrubbed with.
func WithCap(capToml []byte) Option {
	return func(o *Options) {
		o.CapToml = capToml
	}
}

// WithManifest sets the manifest file (as TOML bytes) constants are
// generated from.
func WithManifest(manifestToml []byte) Option {
	return func(o *Options) {
		o.ManifestToml = manifestToml
	}
}

// WithGeoJson sets the GeoJSON constants are generated from.
func WithGeoJson(geoJson []byte) Option {
	return func(o *Options) {
		o.GeoJson = geoJson
	}
}

// WithOutputFile sets the output file of the build.
func WithOutputFile(output string) Option {
	return func(o *Options) {
		o.OutputFile = output
	}
}

// Config is a set of applied options, with the cap and manifest files they
// give parsed.
type Config struct {
	Options
	Cap      *sdk.CapFile      // parsed cap file, nil if none was given
	Manifest *sdk.ManifestFile // parsed manifest file, nil if none was given
}

// NewConfig applies options and parses the cap and manifest files they
// give.
func NewConfig(options ...Option) (*Config, []*CompileError) {
	c := &Config{}
	for _, opt := range options {
		opt(&c.Options)
	}
	var err error
	if c.ManifestToml != nil {
		if c.Manifest, err = sdk.ParseManifestFromBytes(c.ManifestToml); err != nil {
			return nil, []*CompileError{{Err: err}}
		}
	}
	if c.CapToml != nil {
		if c.Cap, err = sdk.ParseCapFromBytes(c.CapToml); err != nil {
			return nil, []*CompileError{{Err: err}}
		}
	}
	return c, nil
}
