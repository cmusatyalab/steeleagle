package vehicle

import (
	"context"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	gabrielpb "github.com/cmusatyalab/gabriel/protocol/go"
	"github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/result"
	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	"github.com/rs/zerolog/log"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Sensor data for input producers.
type Data interface {
	*stream_msg_pb.EncodedFrame | *stream_msg_pb.Telemetry
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
					telBytes, err := proto.Marshal(val)
					if err != nil {
						log.Err(err).Msg("error marshaling data")
					}
					payload := &gabrielpb.InputFrame_BytePayload{
						BytePayload: telBytes,
					}
					frame := &gabrielpb.InputFrame{
						PayloadType: gabrielpb.PayloadType_TEXT,
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

func (v *Vehicle) createGabrielClient() {
	telCh := v.store.subscribeToTelemetry()
	telProducer := getGabrielProducer("telemetry", telCh, []string{"telemetry-engine"})

	consumer := func(res *gabrielpb.Result) {
		cmpRes := &result.ComputeResult{
			Timestamp: timestamppb.Now(),
		}
		v.store.addResult(res.TargetEngineId, cmpRes)
	}

	var err error
	v.gabrielClient, err = gabrielclient.NewGrpcClient(
		"", []*gabrielclient.InputProducer{telProducer}, consumer)
	if err != nil {

	}
}
