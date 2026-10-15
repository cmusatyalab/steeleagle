package vehicle

// The vehicle's side of Gabriel: a local server for the engines on this
// machine, a client that runs the configured flow, a producer for each of the
// vehicle's streams the flow takes, and a subscription to each producer's
// events, which stores the engines' results.
//
// Producers and subscriptions lock their goroutine to its OS thread, so each
// is created, used and closed on a goroutine of its own.

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"net"
	"strings"
	"sync"

	"github.com/BurntSushi/toml"
	gabriel "github.com/cmusatyalab/gabriel/go"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	"github.com/rs/zerolog"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

const (
	// GabrielVehiclePlaceholder stands for the vehicle's name in a flow's
	// names, so that one flow serves every vehicle: Gabriel's names are
	// global to the machine.
	GabrielVehiclePlaceholder = "{vehicle}"
	// GabrielFramesProducer and GabrielTelemetryProducer name the producers
	// of the vehicle's video frames and its telemetry in a flow.
	GabrielFramesProducer    = GabrielVehiclePlaceholder + ".frames"
	GabrielTelemetryProducer = GabrielVehiclePlaceholder + ".telemetry"
	// GabrielLocal and GabrielRemote are where an engine runs.
	GabrielLocal  = "local"
	GabrielRemote = "remote"
	// DefaultGabrielMaxFrameSize fits a 1080p JPEG frame.
	DefaultGabrielMaxFrameSize = 4 << 20
	// gabrielMaxTelemetrySize fits a serialized Telemetry message.
	gabrielMaxTelemetrySize = 64 << 10
)

// forVehicle returns the flow with the vehicle's name in place of
// GabrielVehiclePlaceholder.
func (f GabrielFlow) forVehicle(name string) GabrielFlow {
	expand := func(s string) string {
		return strings.ReplaceAll(s, GabrielVehiclePlaceholder, name)
	}
	out := GabrielFlow{
		Producers: make([]GabrielProducer, len(f.Producers)),
		Engines:   make([]GabrielEngine, len(f.Engines)),
		Edges:     make([]GabrielEdge, len(f.Edges)),
	}
	for i, p := range f.Producers {
		out.Producers[i] = GabrielProducer{Name: expand(p.Name), Tokens: p.Tokens}
	}
	for i, e := range f.Engines {
		out.Engines[i] = GabrielEngine{Name: expand(e.Name), Location: e.Location}
	}
	for i, e := range f.Edges {
		out.Edges[i] = GabrielEdge{From: expand(e.From), To: expand(e.To), Timeout: e.Timeout}
	}
	return out
}

// Validate checks what the vehicle relies on, before Gabriel checks the rest
// when the flow is added: each producer is one of the vehicle's streams, each
// engine runs locally or remotely, and a flow with remote engines has a remote
// server to run them.
func (c GabrielConfig) Validate() error {
	for _, p := range c.Flow.Producers {
		if p.Name != GabrielFramesProducer && p.Name != GabrielTelemetryProducer {
			return fmt.Errorf("gabriel producer %q is not one of the vehicle's streams (%s, %s)",
				p.Name, GabrielFramesProducer, GabrielTelemetryProducer)
		}
	}
	for _, e := range c.Flow.Engines {
		switch e.Location {
		case GabrielLocal:
		case GabrielRemote:
			if c.RemoteServer == "" || len(c.RemoteCertificate) == 0 {
				return fmt.Errorf("gabriel engine %q is remote, but no remote server and certificate are given", e.Name)
			}
		default:
			return fmt.Errorf("gabriel engine %q has location %q, not %q or %q",
				e.Name, e.Location, GabrielLocal, GabrielRemote)
		}
	}
	return nil
}

// enabled reports whether the vehicle runs a Gabriel flow.
func (c GabrielConfig) enabled() bool {
	return len(c.Flow.Producers) > 0
}

// startGabriel starts the vehicle's Gabriel server, client, producers and
// result subscriptions, and adds its flow. They stop when ctx ends.
func (v *Vehicle) startGabriel(ctx context.Context) (err error) {
	cfg := v.gabrielCfg
	if err := cfg.Validate(); err != nil {
		return err
	}
	flow := cfg.Flow.forVehicle(v.Name)
	var spec bytes.Buffer
	if err := toml.NewEncoder(&spec).Encode(flow); err != nil {
		return fmt.Errorf("encoding the gabriel flow: %w", err)
	}

	serverName := v.Name + ".server"
	server, err := gabriel.NewServer(serverName)
	if err != nil {
		return fmt.Errorf("starting the gabriel server: %w", err)
	}
	defer func() {
		if err != nil {
			server.Close()
		}
	}()
	for _, e := range flow.Engines {
		if e.Location == GabrielLocal {
			if err := server.AddEngine(e.Name); err != nil {
				return fmt.Errorf("serving gabriel engine %q: %w", e.Name, err)
			}
		}
	}

	var opts []gabriel.ClientOption
	if cfg.RemoteServer != "" {
		// Gabriel takes an address, not a host name.
		addr, err := net.ResolveUDPAddr("udp", cfg.RemoteServer)
		if err != nil {
			return fmt.Errorf("resolving the gabriel remote server %q: %w", cfg.RemoteServer, err)
		}
		opts = append(opts, gabriel.WithRemoteServer(addr.String(), cfg.RemoteCertificate))
		if cfg.CrossingCapacity > 0 {
			opts = append(opts, gabriel.WithCrossingCapacity(cfg.CrossingCapacity))
		}
	}
	client, err := gabriel.NewClient(v.Name+".client", serverName, opts...)
	if err != nil {
		return fmt.Errorf("starting the gabriel client: %w", err)
	}
	defer func() {
		if err != nil {
			client.Close()
		}
	}()

	// Producers and subscriptions stop before the client and the server.
	streamsCtx, stopStreams := context.WithCancel(ctx)
	var streams sync.WaitGroup
	defer func() {
		if err != nil {
			stopStreams()
			streams.Wait()
		}
	}()
	maxFrameSize := cfg.MaxFrameSize
	if maxFrameSize == 0 {
		maxFrameSize = DefaultGabrielMaxFrameSize
	}
	for i, p := range flow.Producers {
		// Subscribed before the flow is added, so that no result is missed.
		ready := make(chan error, 2)
		published := newPublishTimes(p.Name)
		streams.Go(func() { v.storeGabrielResults(streamsCtx, published, ready) })
		switch cfg.Flow.Producers[i].Name {
		case GabrielFramesProducer:
			frames := v.store.subscribeToFrames()
			streams.Go(func() {
				runGabrielProducer(streamsCtx, published, v.Name, frames, maxFrameSize, ready, v.log)
			})
		case GabrielTelemetryProducer:
			telemetry := v.store.subscribeToTelemetry()
			streams.Go(func() {
				runGabrielProducer(streamsCtx, published, v.Name, telemetry, gabrielMaxTelemetrySize, ready, v.log)
			})
		}
		if err := errors.Join(<-ready, <-ready); err != nil {
			return fmt.Errorf("starting gabriel producer %q: %w", p.Name, err)
		}
		if err := client.AddProducer(p.Name); err != nil {
			return fmt.Errorf("adding gabriel producer %q: %w", p.Name, err)
		}
	}
	if err := client.AddFlow(v.Name, spec.String()); err != nil {
		return fmt.Errorf("adding the gabriel flow: %w", err)
	}
	v.log.Info().Str("remote-server", cfg.RemoteServer).Msg("gabriel flow added")

	go func() {
		<-ctx.Done()
		stopStreams()
		streams.Wait()
		client.Close()
		server.Close()
	}()
	return nil
}

// runGabrielProducer creates the producer published.producer, and publishes
// each message from inputs on flow until ctx ends, noting when in published.
// It reports on ready whether the producer started.
func runGabrielProducer[T proto.Message](
	ctx context.Context,
	published *publishTimes,
	flow string,
	inputs <-chan T,
	maxSize int,
	ready chan<- error,
	log zerolog.Logger,
) {
	name := published.producer
	var zero T // a nil message still describes its type
	inputType := string(zero.ProtoReflect().Descriptor().FullName())
	producer, err := gabriel.NewProducer(name, inputType, maxSize)
	ready <- err
	if err != nil {
		return
	}
	defer producer.Close()
	log = log.With().Str("producer", name).Logger()
	for {
		select {
		case <-ctx.Done():
			return
		case msg := <-inputs:
			if size := proto.Size(msg); size > maxSize {
				log.Warn().Int("bytes", size).Int("max", maxSize).
					Msg("gabriel input too large; dropping it")
				continue
			}
			buf, err := producer.Loan()
			if err != nil {
				log.Err(err).Msg("loaning a gabriel input buffer")
				continue
			}
			// The message fits, so it is written in place.
			out, err := proto.MarshalOptions{}.MarshalAppend(buf[:0], msg)
			if err != nil {
				log.Err(err).Msg("serializing a gabriel input")
				continue
			}
			publishedAt := gabriel.Now()
			seq, err := producer.Publish(flow, len(out))
			if err != nil {
				log.Err(err).Msg("publishing a gabriel input")
				continue
			}
			published.published(seq, publishedAt)
		}
	}
}

// storeGabrielResults subscribes to the events about the inputs of the
// producer published.producer, and stores each engine's newest result and
// records the metrics until ctx ends. It reports on ready whether the
// subscription started.
func (v *Vehicle) storeGabrielResults(ctx context.Context, published *publishTimes, ready chan<- error) {
	producer := published.producer
	events, err := gabriel.SubscribeProducer(producer)
	ready <- err
	if err != nil {
		return
	}
	defer events.Close()
	log := v.log.With().Str("producer", producer).Logger()
	detectionType := string((*resultpb.DetectionResult)(nil).ProtoReflect().Descriptor().FullName())
	metrics := newGabrielMetrics(published)
	for {
		event, err := events.Next(ctx)
		if err != nil {
			if ctx.Err() == nil {
				log.Err(err).Msg("reading gabriel events")
			}
			return
		}
		metrics.record(event)
		switch event.Kind {
		case gabriel.EventResult:
			// A filter that passes or stops an input may have no result.
			if len(event.Result) == 0 {
				continue
			}
			result := resultpb.ComputeResult_builder{Timestamp: timestamppb.Now()}
			detections := &resultpb.DetectionResult{}
			if event.PayloadType == detectionType && proto.Unmarshal(event.Result, detections) == nil {
				result.DetectionResult = detections
			} else {
				result.GenericResult = resultpb.GenericResult_builder{Payload: event.Result}.Build()
			}
			v.store.addResult(event.Engine, result.Build())
		case gabriel.EventDisconnected:
			log.Warn().Str("flow", event.Flow).
				Msg("gabriel lost the connection to a server; reconnecting")
		case gabriel.EventLost:
			log.Warn().Uint64("events", event.Lost).Msg("gabriel events lost; reading fell behind")
		case gabriel.EventTimedOut:
			log.Debug().Str("engine", event.Engine).Uint64("seq", event.ID.Seq).
				Msg("gabriel engine timed out")
		}
	}
}
