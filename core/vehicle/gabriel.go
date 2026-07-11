package vehicle

import (
	"context"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	gabriel_pb "github.com/cmusatyalab/gabriel/protocol/go"
	"github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/result"
	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	"github.com/rs/zerolog/log"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

func createFrameProducer(
    frameCh <-chan *stream_msg_pb.EncodedFrame) *gabrielclient.InputProducer {
	return nil
}

func createTelemetryProducer(
	telCh <-chan *stream_msg_pb.Telemetry) *gabrielclient.InputProducer {

	producer := func(ctx context.Context) <-chan *gabriel_pb.InputFrame {
		ch := make(chan *gabriel_pb.InputFrame, 1)
		go func() {
			for {
				select {
				case <-ctx.Done():
					return
				case tel := <-telCh:
					telBytes, err := proto.Marshal(tel)
					if err != nil {
						log.Err(err).Msg("error marshaling telemetry")
					}
					payload := &gabriel_pb.InputFrame_BytePayload{
						BytePayload: telBytes,
					}
					frame := &gabriel_pb.InputFrame{
						PayloadType: gabriel_pb.PayloadType_TEXT,
						Payload:     payload,
					}
					ch <- frame
				}
			}
		}()
		return ch
	}
	return gabrielclient.NewInputProducer("telemetry", producer, []string{"telemetry-engine"})
}

func (v *Vehicle) createGabrielClient() {
	telCh := v.store.subscribeToTelemetry()
	telProducer := createTelemetryProducer(telCh)

	consumer := func(res *gabriel_pb.Result) {
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
