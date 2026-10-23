// Package feed reads the frames and telemetry that dataflows send the GCS's
// Uriel engine.
package feed

import (
	"context"
	"fmt"
	"strings"

	framepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/frame"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	"google.golang.org/protobuf/proto"
)

const (
	// FrameType is the payload type of encoded frames.
	FrameType = "steeleagle_protocol/v1/messages/frame/EncodedFrame"
	// TelemetryType is the payload type of telemetry.
	TelemetryType = "steeleagle_protocol/v1/messages/telemetry/Telemetry"
	// telemetrySuffix ends the name of every vehicle's telemetry producer,
	// "<vehicle>.telemetry".
	telemetrySuffix = ".telemetry"
)

// Message is one input of the engine: a frame or telemetry of a vehicle.
type Message struct {
	// Producer is the producer the input came from, e.g. "drone1.front" for
	// a camera or "drone1.telemetry".
	Producer string
	// Vehicle is the vehicle the producer belongs to.
	Vehicle string
	// Seq is the input's sequence number from its producer.
	Seq uint64
	// Exactly one of Frame and Telemetry is set.
	Frame     *framepb.EncodedFrame
	Telemetry *telemetrypb.Telemetry
}

// VehicleOf returns the vehicle that producer belongs to. Producers are named
// "<vehicle>.<camera>" or "<vehicle>.telemetry", so a vehicle whose name has
// a dot in it is only told apart by its telemetry.
func VehicleOf(producer string) string {
	if vehicle, ok := strings.CutSuffix(producer, telemetrySuffix); ok {
		return vehicle
	}
	vehicle, _, _ := strings.Cut(producer, ".")
	return vehicle
}

// Decode reads the input data of payloadType from producer. An input without
// a payload type is telemetry if it comes from a telemetry producer, and a
// frame otherwise.
func Decode(producer, payloadType string, data []byte) (Message, error) {
	msg := Message{Producer: producer, Vehicle: VehicleOf(producer)}
	if payloadType == "" {
		payloadType = FrameType
		if strings.HasSuffix(producer, telemetrySuffix) {
			payloadType = TelemetryType
		}
	}
	var m proto.Message
	switch payloadType {
	case FrameType:
		msg.Frame = &framepb.EncodedFrame{}
		m = msg.Frame
	case TelemetryType:
		msg.Telemetry = &telemetrypb.Telemetry{}
		m = msg.Telemetry
	default:
		return Message{}, fmt.Errorf("unsupported payload type %q", payloadType)
	}
	// Unmarshal copies the data, which only lives until the input is dropped
	if err := proto.Unmarshal(data, m); err != nil {
		return Message{}, fmt.Errorf("could not decode %s: %w", payloadType, err)
	}
	return msg, nil
}

// Run creates the Uriel engine name, and hands each of its inputs to handle
// until ctx is done, returning nil then. The engine is a sink: it drops every
// input, so handle must not block it for long. Run keeps its goroutine on one
// OS thread, as Uriel requires.
func Run(ctx context.Context, name string, maxInputSize int, log zerolog.Logger, handle func(Message)) error {
	engine, err := uriel.NewEngine(name, "", maxInputSize)
	if err != nil {
		return fmt.Errorf("could not create engine %q: %w", name, err)
	}
	defer engine.Close()
	log.Info().Str("engine", name).Msg("reading frames and telemetry")
	for {
		in, err := engine.Next(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return fmt.Errorf("could not read input: %w", err)
		}
		msg, decodeErr := Decode(in.ID.Producer, in.PayloadType, in.Data)
		if err := engine.Drop(nil); err != nil {
			return fmt.Errorf("could not drop input: %w", err)
		}
		if decodeErr != nil {
			log.Warn().Err(decodeErr).Str("producer", in.ID.Producer).Uint64("seq", in.ID.Seq).Msg("skipping input")
			continue
		}
		msg.Seq = in.ID.Seq
		handle(msg)
	}
}
