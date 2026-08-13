package vehicle

import (
	"context"
	"fmt"
	"net"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	gabrielpb "github.com/cmusatyalab/gabriel/protocol/go"
	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
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
					select {
					case ch <- frame:
					default:
						// drain frame already in channel, if any
						select {
						case <-ch:
						default:
						}
						// now the channel should be empty
						select {
						case ch <- frame:
						default:
						}
					}
				}
			}
		}()
		return ch
	}
	return gabrielclient.NewInputProducer(producerName, producer, targetEngines)
}

// Create a Gabriel client with telemetry and video frame input producers.
// Either producer is left out entirely if its target engine list is empty.
func (v *Vehicle) createGabrielClient() error {
	var producers []*gabrielclient.InputProducer
	if len(v.gabrielCfg.TelemetryTargetEngines) > 0 {
		telCh := v.store.subscribeToTelemetry()
		producers = append(producers, getGabrielProducer(
			"telemetry",
			telCh,
			v.gabrielCfg.TelemetryTargetEngines))
	}
	if len(v.gabrielCfg.VideoFramesTargetEngines) > 0 {
		frameCh := v.store.subscribeToFrames()
		producers = append(producers, getGabrielProducer(
			"frames",
			frameCh,
			v.gabrielCfg.VideoFramesTargetEngines))
	}
	if len(producers) == 0 {
		return fmt.Errorf("gabriel.server-endpoint is set but neither telemetry-target-engines nor video-frames-target-engines names an engine")
	}

	consumer := func(res *gabrielpb.Result) {
		cmpRes := resultpb.ComputeResult_builder{
			Timestamp: timestamppb.Now(),
		}.Build()
		v.store.addResult(res.TargetEngineId, cmpRes)
	}

	opts := []gabrielclient.Option{
		gabrielclient.WithClientInfo(commonpb.VehicleInfo_builder{
			VehicleId: v.Name,
			Model:     v.Model,
		}.Build()),
	}
	if v.gabrielCfg.PrometheusPort != 0 {
		opts = append(opts, gabrielclient.WithPrometheusPort(v.gabrielCfg.PrometheusPort))
	}
	if v.dialer != nil {
		// Sources the connection from the vehicle's own tsnet node (if any)
		opts = append(opts, gabrielclient.WithDialOptions(grpc.WithContextDialer(
			func(ctx context.Context, addr string) (net.Conn, error) {
				return v.dialer(ctx, "tcp", addr)
			},
		)))
	}

	client, err := gabrielclient.NewGrpcClient(
		v.gabrielCfg.ServerEndpoint,
		producers,
		consumer,
		opts...)
	if err != nil {
		return err
	}
	v.gabrielClient = client
	return nil
}
