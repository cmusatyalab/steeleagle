package vehicle

import (
	"context"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	gabrielpb "github.com/cmusatyalab/gabriel/protocol/go"
	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/rs/zerolog/log"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Sensor data for input producers.
type Data interface {
	*telemetrypb.EncodedFrame | *telemetrypb.Telemetry
	proto.Message
}

// Construct a Gabriel input producer with the given name that uses the
// provided channel to produce its inputs, targeting the specified engines.
func getGabrielProducer[T Data](
	producerName string,
	inputCh <-chan T,
	targetEngines []string) *gabrielclient.InputProducer {

	producer := func(ctx context.Context) <-chan *gabrielpb.InputFrame {
		ch := make(chan *gabrielpb.InputFrame, 1)
		go func() {
			for {
				select {
				case <-ctx.Done():
					return
				case val := <-inputCh:
					anyPayload, err := anypb.New(val)
					if err != nil {
						log.Err(err).Msg("error packing data into Any")
						continue
					}
					payload := &gabrielpb.InputFrame_AnyPayload{
						AnyPayload: anyPayload,
					}
					payloadType := gabrielpb.PayloadType_TEXT
					if _, ok := any(val).(*telemetrypb.EncodedFrame); ok {
						payloadType = gabrielpb.PayloadType_IMAGE
					}
					frame := &gabrielpb.InputFrame{
						PayloadType: payloadType,
						Payload:     payload,
					}
					ch <- frame
				}
			}
		}()
		return ch
	}
	return gabrielclient.NewInputProducer(producerName, producer, targetEngines)
}

// Create a Gabriel client with telemetry and video frame input producers.
func (v *Vehicle) createGabrielClient() error {
	telCh := v.store.subscribeToTelemetry()
	telProducer := getGabrielProducer(
		"telemetry",
		telCh,
		v.gabrielCfg.TelemetryTargetEngines)

	frameCh := v.store.subscribeToFrames()
	frameProducer := getGabrielProducer(
		"frames",
		frameCh,
		v.gabrielCfg.VideoFramesTargetEngines)

	consumer := func(res *gabrielpb.Result) {
		cmpRes := &resultpb.ComputeResult{
			Timestamp: timestamppb.Now(),
		}
		v.store.addResult(res.TargetEngineId, cmpRes)
	}

	client, err := gabrielclient.NewGrpcClient(
		v.gabrielCfg.ServerEndpoint,
		[]*gabrielclient.InputProducer{telProducer, frameProducer},
		consumer,
		gabrielclient.WithClientInfo(&commonpb.VehicleInfo{
			VehicleId: v.Name,
			Model:     v.Model,
		}))
	if err != nil {
		return err
	}
	v.gabrielClient = client
	return nil
}
