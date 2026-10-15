package vehicle

import (
	"github.com/cmusatyalab/steeleagle/core/util"
)

type PolicyConfig struct {
	Law ControlLaw
}

type PluginConfig struct {
	Driver  util.Plugin
	Mission util.Plugin
	Plugins []util.Plugin
}

// GabrielConfig configures the Gabriel flow the vehicle runs. A flow without
// producers leaves Gabriel off.
type GabrielConfig struct {
	// Flow is the flow, with GabrielVehiclePlaceholder standing for the
	// vehicle's name in its names.
	Flow GabrielFlow
	// RemoteServer is the host:port of the remote gabriel-server, for flows
	// with remote engines. Gabriel connects to it over QUIC itself, so the
	// host's own network must reach it, and its own DNS resolve it.
	RemoteServer string
	// RemoteCertificate is the remote server's certificate, in DER: a copy of
	// the certificate.der in its identity directory.
	RemoteCertificate []byte
	// CrossingCapacity is how many inputs each crossing to the remote server
	// may have in flight. Left unset (0), Gabriel picks its default.
	CrossingCapacity int
	// MaxFrameSize is the largest serialized frame the vehicle sends, in
	// bytes. Left unset (0), DefaultGabrielMaxFrameSize.
	MaxFrameSize int
	// RecordDir is where the vehicle records every input and event of its
	// flow, a directory per start of the flow. Left unset (""), it records
	// nothing.
	RecordDir string
}

// GabrielFlow describes a Gabriel flow: its producers, its engines and where
// each runs, and the edges between them. It mirrors Gabriel's flow spec.
type GabrielFlow struct {
	Producers []GabrielProducer `toml:"producers"`
	Engines   []GabrielEngine   `toml:"engines"`
	Edges     []GabrielEdge     `toml:"edges"`
}

// GabrielProducer is a producer of a flow: one of the vehicle's streams,
// GabrielFramesProducer or GabrielTelemetryProducer.
type GabrielProducer struct {
	Name string `toml:"name"`
	// Tokens is how many of the producer's inputs may be in the flow at once.
	// Left unset (0), Gabriel computes it from the flow.
	Tokens int `toml:"tokens,omitzero"`
}

// GabrielEngine is an engine of a flow.
type GabrielEngine struct {
	Name string `toml:"name"`
	// Location is GabrielLocal, on the vehicle's machine, or GabrielRemote,
	// on the remote server.
	Location string `toml:"location"`
}

// GabrielEdge carries inputs from a producer or an engine to an engine.
type GabrielEdge struct {
	From string `toml:"from"`
	To   string `toml:"to"`
	// Timeout is how long the engine at To may take for an input, e.g. "1s".
	Timeout string `toml:"timeout"`
}

type VideoStreamConfig struct {
	Codec      string
	Resolution VideoResolution
	StreamType VideoStreamType
	// Fps is the desired frame rate. If zero, the vehicle stream runs
	// unthrottled at whatever rate the driver (or FFmpeg) produces frames.
	Fps uint32
}
