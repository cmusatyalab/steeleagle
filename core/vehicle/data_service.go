package vehicle

import (
	"bytes"
	"context"
	"errors"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	uriel "github.com/cmusatyalab/uriel/go"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
)

// Engine is an engine that the vehicle's dataflows can use.
type Engine struct {
	Inputs []string // input types the engine accepts
	Result string   // result type the engine generates
	Local  bool     // whether the engine is served by the local compute service, rather than the remote one
}

// location is the engine's location, as dataflows give it.
func (e Engine) location() string {
	if e.Local {
		return LocalLocation
	}
	return RemoteLocation
}

// dataflow is a dataflow installed on the vehicle's Uriel client, under the
// vehicle's name.
type dataflow struct {
	toml      []byte                         // dataflow TOML, as it was given to SetDataflow
	spec      string                         // Uriel flow spec TOML, with fully qualified producers
	producers []string                       // fully qualified producers that feed the flow
	cameras   *driverpb.StreamCamerasRequest // cameras the driver streams for the flow
}

// SetDataflow parses and executes a dataflow from TOML bytes. A dataflow with
// the same TOML as the current one is already set, so nothing is done.
func (v *Vehicle) SetDataflow(
	ctx context.Context,
	req *vehiclepb.SetDataflowRequest,
) (*vehiclepb.SetDataflowResponse, error) {
	v.flowMu.Lock()
	defer v.flowMu.Unlock()

	if v.flow != nil && bytes.Equal(v.flow.toml, req.GetToml()) {
		v.log.Debug().Msg("dataflow unchanged")
		return &vehiclepb.SetDataflowResponse{}, nil
	}
	flow, err := v.parseDataflow(req.GetToml())
	if err != nil {
		v.log.Error().Err(err).Msg("could not parse dataflow")
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}
	flow.toml = req.GetToml()

	// The driver streams the flow's cameras before the flow is set, so a flow
	// it can't stream is not set
	if err := v.streamCameras(ctx, flow.cameras); err != nil {
		v.log.Error().Err(err).Msg("could not stream dataflow cameras")
		return nil, err
	}

	// Replace the current dataflow, which shares the vehicle's name
	old := v.flow
	if old != nil {
		v.unsubscribe()
		if err := v.uriel.RemoveFlow(v.Name); err != nil {
			v.log.Error().Err(err).Msg("could not remove current dataflow")
			if subs, err := v.subscribe(v.runCtx, old); err == nil {
				v.flowSubs = subs
			}
			return nil, status.Error(codes.Internal, err.Error())
		}
		v.flow = nil
	}
	if err := v.installDataflow(flow); err != nil {
		v.log.Error().Err(err).Msg("could not set dataflow")
		// The driver goes back to the cameras of the previous dataflow, or none
		cameras := &driverpb.StreamCamerasRequest{}
		if old != nil {
			if err := v.installDataflow(old); err != nil {
				v.log.Error().Err(err).Msg("could not restore previous dataflow")
			} else {
				cameras = old.cameras
			}
		}
		if err := v.streamCameras(ctx, cameras); err != nil {
			v.log.Error().Err(err).Msg("could not restore previous dataflow cameras")
		}
		if errors.Is(err, uriel.ErrInvalid) {
			return nil, status.Error(codes.InvalidArgument, err.Error())
		}
		return nil, status.Error(codes.Internal, err.Error())
	}
	v.log.Info().Strs("producers", flow.producers).Msg("dataflow set")
	return &vehiclepb.SetDataflowResponse{}, nil
}

// GetFlow returns the TOML of the current dataflow, as it was given to
// SetDataflow, or empty TOML if no dataflow is set.
func (v *Vehicle) GetFlow(
	ctx context.Context,
	req *vehiclepb.GetFlowRequest,
) (*vehiclepb.GetFlowResponse, error) {
	v.flowMu.Lock()
	defer v.flowMu.Unlock()
	var toml []byte
	if v.flow != nil {
		toml = v.flow.toml
	}
	return vehiclepb.GetFlowResponse_builder{Toml: toml}.Build(), nil
}

// GetResult queries the results of an engine: the most recent one, or all
// those between the start and end times, if either is given, ordered from
// oldest to newest. It fails with NotFound for an engine that never produced
// a result.
func (v *Vehicle) GetResult(
	ctx context.Context,
	req *vehiclepb.GetResultRequest,
) (*vehiclepb.GetResultResponse, error) {
	engine := req.GetEngine()
	if engine == "" || engine == TelemetryBucket {
		return nil, status.Errorf(codes.InvalidArgument, "%q is not an engine", engine)
	}
	var results []*resultpb.ComputeResult
	err := v.query(engine, req.GetTimeStart(), req.GetTimeEnd(), func(value []byte) error {
		result := &resultpb.ComputeResult{}
		if err := proto.Unmarshal(value, result); err != nil {
			return err
		}
		results = append(results, result)
		return nil
	})
	if status.Code(err) == codes.NotFound {
		return nil, err
	} else if err != nil {
		v.log.Error().Err(err).Str("engine", engine).Msg("could not query results")
		return nil, err
	}
	return vehiclepb.GetResultResponse_builder{Result: results}.Build(), nil
}

// GetTelemetry queries received telemetry: the most recent, or all of it
// between the start and end times, if either is given, ordered from oldest to
// newest.
func (v *Vehicle) GetTelemetry(
	ctx context.Context,
	req *vehiclepb.GetTelemetryRequest,
) (*vehiclepb.GetTelemetryResponse, error) {
	var telemetry []*telemetrypb.Telemetry
	err := v.query(TelemetryBucket, req.GetTimeStart(), req.GetTimeEnd(), func(value []byte) error {
		t := &telemetrypb.Telemetry{}
		if err := proto.Unmarshal(value, t); err != nil {
			return err
		}
		telemetry = append(telemetry, t)
		return nil
	})
	// Before any telemetry is received there is just none
	if status.Code(err) == codes.NotFound {
		err = nil
	}
	if err != nil {
		v.log.Error().Err(err).Msg("could not query telemetry")
		return nil, err
	}
	return vehiclepb.GetTelemetryResponse_builder{Telemetry: telemetry}.Build(), nil
}

// readTelemetry stores the telemetry the driver publishes until ctx is done.
// Whether the reader was created is sent on ready.
func (v *Vehicle) readTelemetry(ctx context.Context, ready chan<- error) {
	defer v.dataWg.Done()
	producer := v.telemetryUri()
	reader, err := uriel.NewReader(producer)
	ready <- err
	if err != nil {
		return
	}
	// A reader must be closed on the goroutine that created it
	defer reader.Close()
	for {
		input, err := reader.Next(ctx)
		if err != nil {
			if ctx.Err() == nil {
				v.log.Error().Err(err).Str("producer", producer).Msg("telemetry reader failed")
			}
			return
		}
		if input.Lost > 0 {
			v.log.Warn().Uint64("lost", input.Lost).Msg("telemetry reader fell behind")
		}
		// Data is only valid until the next poll, but the write is done by then
		if err := v.store(TelemetryBucket, time.Now(), input.Data); err != nil {
			v.log.Error().Err(err).Msg("could not store telemetry")
		}
	}
}

// installDataflow adds flow to the Uriel client under the vehicle's name, and
// subscribes to its results. The caller must hold flowMu, and the current
// dataflow must already be removed.
func (v *Vehicle) installDataflow(flow *dataflow) error {
	for _, producer := range flow.producers {
		if v.producers[producer] {
			continue
		}
		if err := v.uriel.AddProducer(producer); err != nil {
			return err
		}
		v.producers[producer] = true
	}
	subs, err := v.subscribe(v.runCtx, flow)
	if err != nil {
		return err
	}
	if err := v.uriel.AddFlow(v.Name, flow.spec); err != nil {
		subs.cancel()
		subs.wg.Wait()
		return err
	}
	v.flow, v.flowSubs = flow, subs
	return nil
}

// streamTelemetry asks the driver to publish telemetry, if it supports
// streaming it.
func (v *Vehicle) streamTelemetry(ctx context.Context) error {
	if !v.Config.Driver.Supports(StreamTelemetryMethod) {
		v.log.Warn().Msg("driver does not stream telemetry")
		return nil
	}
	ctx, cancel := context.WithTimeout(ctx, StreamTimeout)
	defer cancel()
	req := driverpb.StreamTelemetryRequest_builder{Uri: v.telemetryUri()}.Build()
	// The driver's server may not be ready right after it starts
	_, err := driverpb.NewStreamServiceClient(v.driver.conn).StreamTelemetry(ctx, req, grpc.WaitForReady(true))
	return err
}

// streamCameras asks the driver to stream cameras, replacing those it
// streamed before. A driver that doesn't support streaming cameras is only
// asked for none.
func (v *Vehicle) streamCameras(ctx context.Context, req *driverpb.StreamCamerasRequest) error {
	if !v.Config.Driver.Supports(StreamCamerasMethod) {
		if req.HasPrimary() || len(req.GetSecondaries()) > 0 {
			return status.Error(codes.FailedPrecondition, "driver does not stream cameras")
		}
		return nil
	}
	ctx, cancel := context.WithTimeout(ctx, StreamTimeout)
	defer cancel()
	_, err := driverpb.NewStreamServiceClient(v.driver.conn).StreamCameras(ctx, req, grpc.WaitForReady(true))
	return err
}

// telemetryUri is the fully qualified name the driver publishes telemetry on.
func (v *Vehicle) telemetryUri() string {
	return v.Name + "." + TelemetryProducerName
}
