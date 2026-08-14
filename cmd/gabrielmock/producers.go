package main

import (
	"context"
	"time"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	gabrielpb "github.com/cmusatyalab/gabriel/protocol/go"
	"github.com/rs/zerolog/log"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"
)

// newTickerProducer builds a Gabriel InputProducer that calls build once per
// tick of the given interval, packs the resulting message as the given
// payload type, and logs each send. It mirrors the shape of
// core/vehicle/gabriel.go's getGabrielProducer, but generates its own data on
// a ticker instead of relaying an upstream channel, since there is no real
// driver behind it.
func newTickerProducer(
	name string,
	targetEngines []string,
	interval time.Duration,
	payloadType gabrielpb.PayloadType,
	build func() proto.Message,
	stats *producerStats) *gabrielclient.InputProducer {

	producerFunc := func(ctx context.Context) <-chan *gabrielpb.InputFrame {
		ch := make(chan *gabrielpb.InputFrame, 1)
		go func() {
			defer close(ch)
			ticker := time.NewTicker(interval)
			defer ticker.Stop()
			for {
				select {
				case <-ctx.Done():
					return
				case sentAt := <-ticker.C:
					msg := build()
					anyPayload, err := anypb.New(msg)
					if err != nil {
						log.Err(err).Str("producer", name).Msg("error packing payload into Any")
						continue
					}
					frame := &gabrielpb.InputFrame{
						PayloadType: payloadType,
						Payload: &gabrielpb.InputFrame_AnyPayload{
							AnyPayload: anyPayload,
						},
					}
					select {
					case ch <- frame:
						size := proto.Size(msg)
						stats.record(size)
						log.Info().
							Str("producer", name).
							Time("sent_at", sentAt).
							Int("size_bytes", size).
							Msg("sent frame")
					case <-ctx.Done():
						return
					}
				}
			}
		}()
		return ch
	}
	return gabrielclient.NewInputProducer(name, producerFunc, targetEngines)
}

func newTelemetryProducer(targetEngines []string, hz float64, stats *producerStats) *gabrielclient.InputProducer {
	var seq uint64
	build := func() proto.Message {
		seq++
		return syntheticTelemetry(seq)
	}
	return newTickerProducer("telemetry", targetEngines, hzToInterval(hz), gabrielpb.PayloadType_TEXT, build, stats)
}

func newFrameProducer(targetEngines []string, hz float64, vehicle string, width, height, quality int, stats *producerStats) *gabrielclient.InputProducer {
	var seq uint64
	build := func() proto.Message {
		seq++
		return syntheticFrame(vehicle, seq, width, height, quality)
	}
	return newTickerProducer("frames", targetEngines, hzToInterval(hz), gabrielpb.PayloadType_IMAGE, build, stats)
}
