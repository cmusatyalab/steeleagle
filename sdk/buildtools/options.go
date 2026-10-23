package buildtools

import (
	"errors"

	"github.com/cmusatyalab/steeleagle/config"
)

// Options are the options for building against the SDK, shared by SDK
// builds and DSL mission compiles.
type Options struct {
	PluginToml   []byte
	ManifestToml []byte
	GeoJson      []byte
	FlowToml     []byte
	OutputFile   string
}

type Option func(*Options)

// WithPlugin sets the driver plugin config (as TOML bytes) whose driver cap the
// SDK is scrubbed with, and camera constants are generated from.
func WithPlugin(pluginToml []byte) Option {
	return func(o *Options) {
		o.PluginToml = pluginToml
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

// WithFlow sets the dataflow config (as TOML bytes) whose leaf engines
// constants are generated from, which a DSL mission also embeds and sets on
// the vehicle each time it is started.
func WithFlow(flowToml []byte) Option {
	return func(o *Options) {
		o.FlowToml = flowToml
	}
}

// WithOutputFile sets the output file of the build.
func WithOutputFile(output string) Option {
	return func(o *Options) {
		o.OutputFile = output
	}
}

// Config is a set of applied options, with the cap, manifest and flow files
// they give parsed.
type Config struct {
	Options
	Cap      *config.DriverCap       // driver cap of the plugin config, nil if none was given
	Manifest *config.MissionManifest // parsed manifest file, nil if none was given
	Flow     *config.FlowConfig      // parsed flow file, nil if none was given
}

// NewConfig applies options and parses the cap, manifest and flow files they
// give.
func NewConfig(options ...Option) (*Config, []*CompileError) {
	c := &Config{}
	for _, opt := range options {
		opt(&c.Options)
	}
	var err error
	if c.ManifestToml != nil {
		if c.Manifest, err = config.ParseMissionManifestFromBytes(c.ManifestToml); err != nil {
			return nil, []*CompileError{{Err: err}}
		}
	}
	if c.FlowToml != nil {
		if c.Flow, err = config.ParseFlowConfigFromBytes(c.FlowToml); err != nil {
			return nil, []*CompileError{{Err: err}}
		}
	}
	if c.PluginToml != nil {
		plugin, err := config.ParsePluginConfigFromBytes(c.PluginToml)
		if err != nil {
			return nil, []*CompileError{{Err: err}}
		}
		if plugin.Driver == nil {
			return nil, []*CompileError{{Err: errors.New("plugin config has no [driver] table")}}
		}
		c.Cap = plugin.Driver
	}
	return c, nil
}
