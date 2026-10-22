package vehicle

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"path/filepath"
	"sync"
	"time"

	"github.com/BurntSushi/toml"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	uriel "github.com/cmusatyalab/uriel/go"
	bolt "go.etcd.io/bbolt"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// subscribers are the goroutines that store the results of a dataflow.
type subscribers struct {
	cancel context.CancelFunc
	wg     sync.WaitGroup
}

// parseDataflow reads a Uriel flow spec whose producers are named after the
// vehicle's cameras. They are renamed to their fully qualified names, {vehicle
// name}.{camera name}, in the producers and the edges that start at them, and
// the cameras to stream are worked out; at most one may be a primary camera.
// Every engine must be an available engine, at its location. Uriel checks the
// rest when the flow is added.
func (v *Vehicle) parseDataflow(spec []byte) (*dataflow, error) {
	var parsed map[string]any
	if _, err := toml.Decode(string(spec), &parsed); err != nil {
		return nil, fmt.Errorf("invalid dataflow: %w", err)
	}
	tables := func(key string) ([]map[string]any, error) {
		value, ok := parsed[key]
		if !ok {
			return nil, nil
		}
		list, ok := value.([]map[string]any)
		if !ok {
			return nil, fmt.Errorf("invalid dataflow: %s must be an array of tables", key)
		}
		return list, nil
	}
	producers, err := tables("producers")
	if err != nil {
		return nil, err
	}
	engines, err := tables("engines")
	if err != nil {
		return nil, err
	}
	edges, err := tables("edges")
	if err != nil {
		return nil, err
	}
	for _, e := range engines {
		name, _ := e["name"].(string)
		engine, ok := v.engines[name]
		if !ok {
			return nil, fmt.Errorf("engine %q is not an available engine", name)
		}
		location, _ := e["location"].(string)
		if want := engine.location(); location != want {
			return nil, fmt.Errorf("engine %q is at location %q, not %q", name, want, location)
		}
	}

	cameras := make(map[string]config.DriverCamera)
	for _, c := range v.Config.Driver.Cameras {
		cameras[c.Name] = c
	}
	flow := &dataflow{cameras: &driverpb.StreamCamerasRequest{}}
	var secondaries []*driverpb.CameraRequest
	renamed := make(map[string]string)
	for _, p := range producers {
		name, _ := p["name"].(string)
		camera, ok := cameras[name]
		if !ok {
			return nil, fmt.Errorf("producer %q is not a camera of the vehicle", name)
		}
		uri := v.Name + "." + name
		p["name"] = uri
		renamed[name] = uri
		flow.producers = append(flow.producers, uri)
		request := driverpb.CameraRequest_builder{Id: name, Uri: uri}.Build()
		if !camera.Primary {
			secondaries = append(secondaries, request)
			continue
		}
		if flow.cameras.HasPrimary() {
			return nil, fmt.Errorf("cameras %q and %q are both primary cameras",
				flow.cameras.GetPrimary().GetId(), name)
		}
		flow.cameras.SetPrimary(request)
	}
	flow.cameras.SetSecondaries(secondaries)
	for _, e := range edges {
		if from, ok := e["from"].(string); ok {
			if uri, ok := renamed[from]; ok {
				e["from"] = uri
			}
		}
	}

	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(parsed); err != nil {
		return nil, fmt.Errorf("invalid dataflow: %w", err)
	}
	flow.spec = buf.String()
	return flow, nil
}

// startData opens the data database, starts recording telemetry, and starts
// the subscribers of the current dataflow, if any.
func (v *Vehicle) startData(ctx context.Context) error {
	dir, err := util.GetVehicleDataDirByName(v.Name)
	if err != nil {
		return err
	}
	v.db, err = bolt.Open(filepath.Join(dir, DataDbName), 0600, &bolt.Options{Timeout: time.Second})
	if err != nil {
		return err
	}

	ready := make(chan error, 1)
	v.dataWg.Add(1)
	go v.readTelemetry(ctx, ready)
	if err := <-ready; err != nil {
		return err
	}

	v.flowMu.Lock()
	defer v.flowMu.Unlock()
	if v.flow != nil {
		v.flowSubs, err = v.subscribe(ctx, v.flow)
		if err != nil {
			return err
		}
	}
	return nil
}

// stopData stops recording, once the run context is canceled, and closes the
// data database.
func (v *Vehicle) stopData() {
	v.flowMu.Lock()
	v.unsubscribe()
	v.flowMu.Unlock()
	v.dataWg.Wait()
	if v.db != nil {
		if err := v.db.Close(); err != nil {
			v.log.Warn().Err(err).Msg("could not close data database")
		}
		v.db = nil
	}
}

// subscribe starts a subscriber for each producer of flow, which stores the
// results of the flow's engines until ctx is done or they are unsubscribed.
func (v *Vehicle) subscribe(ctx context.Context, flow *dataflow) (*subscribers, error) {
	ctx, cancel := context.WithCancel(ctx)
	subs := &subscribers{cancel: cancel}
	ready := make(chan error, len(flow.producers))
	for _, producer := range flow.producers {
		subs.wg.Add(1)
		go v.storeResults(ctx, producer, &subs.wg, ready)
	}
	var errs []error
	for range flow.producers {
		errs = append(errs, <-ready)
	}
	if err := errors.Join(errs...); err != nil {
		cancel()
		subs.wg.Wait()
		return nil, err
	}
	return subs, nil
}

// unsubscribe stops the subscribers of the current dataflow, if any. The
// caller must hold flowMu.
func (v *Vehicle) unsubscribe() {
	if v.flowSubs == nil {
		return
	}
	v.flowSubs.cancel()
	v.flowSubs.wg.Wait()
	v.flowSubs = nil
}

// storeResults stores the results of the dataflow's engines for the inputs of
// producer until ctx is done, in a bucket per engine.
func (v *Vehicle) storeResults(
	ctx context.Context,
	producer string,
	wg *sync.WaitGroup,
	ready chan<- error,
) {
	defer wg.Done()
	sub, err := uriel.SubscribeProducer(producer)
	ready <- err
	if err != nil {
		return
	}
	// A subscription must be closed on the goroutine that created it
	defer sub.Close()
	for {
		event, err := sub.Next(ctx)
		if err != nil {
			if ctx.Err() == nil {
				v.log.Error().Err(err).Str("producer", producer).Msg("dataflow subscription failed")
			}
			return
		}
		switch event.Kind {
		case uriel.EventResult, uriel.EventDerived:
			// The producer may also feed flows of other clients
			if event.Flow != v.Name || event.Engine == "" || len(event.Result) == 0 {
				continue
			}
			t := time.Now()
			if !event.ReceivedAt.IsZero() {
				t = time.Now().Add(-uriel.Now().Sub(event.ReceivedAt))
			}
			// The engine is available, since the dataflow was checked
			engine := v.engines[event.Engine]
			result := &resultpb.ComputeResult{}
			if err := setResult(result, engine.Result, event.Result); err != nil {
				v.log.Warn().Err(err).Str("engine", event.Engine).Str("type", engine.Result).
					Msg("result is not of the engine's result type, storing it as generic")
				result.SetGenericResult(resultpb.GenericResult_builder{Payload: event.Result}.Build())
			}
			result.SetSequenceNum(event.ID.Seq)
			result.SetLocal(engine.Local)
			result.SetTimestamp(timestamppb.New(t))
			value, err := proto.Marshal(result)
			if err == nil {
				err = v.store(event.Engine, t, value)
			}
			if err != nil {
				v.log.Error().Err(err).Str("engine", event.Engine).Msg("could not store result")
			}
		case uriel.EventLost:
			v.log.Warn().Uint64("lost", event.Lost).Str("producer", producer).
				Msg("dataflow subscription fell behind")
		case uriel.EventDisconnected:
			if event.Flow == v.Name {
				v.log.Warn().Str("producer", producer).Msg("dataflow lost connection to a compute service")
			}
		}
	}
}

// setResult unmarshals data as resultType, the result type of the engine
// that generated it, into result. A result of an unknown type is set as a
// generic result.
func setResult(result *resultpb.ComputeResult, resultType string, data []byte) error {
	switch resultType {
	case DetectionResultType:
		return unmarshalResult(data, &resultpb.DetectionResult{}, result.SetDetectionResult)
	case ClassificationResultType:
		return unmarshalResult(data, &resultpb.ClassificationResult{}, result.SetClassificationResult)
	case GuidanceResultType:
		return unmarshalResult(data, &resultpb.GuidanceResult{}, result.SetGuidanceResult)
	case PositionResultType:
		return unmarshalResult(data, &resultpb.PositionResult{}, result.SetPositionResult)
	case GenericResultType:
		return unmarshalResult(data, &resultpb.GenericResult{}, result.SetGenericResult)
	}
	result.SetGenericResult(resultpb.GenericResult_builder{Payload: data}.Build())
	return nil
}

// unmarshalResult unmarshals data into m, and sets it with set.
func unmarshalResult[T proto.Message](data []byte, m T, set func(T)) error {
	if err := proto.Unmarshal(data, m); err != nil {
		return err
	}
	set(m)
	return nil
}

// store writes value to bucket under time at. Keys are the time in Unix
// nanoseconds followed by a sequence number, both big endian, so that they
// sort by time and never collide.
func (v *Vehicle) store(bucket string, at time.Time, value []byte) error {
	return v.db.Update(func(tx *bolt.Tx) error {
		b, err := tx.CreateBucketIfNotExists([]byte(bucket))
		if err != nil {
			return err
		}
		seq, err := b.NextSequence()
		if err != nil {
			return err
		}
		key := binary.BigEndian.AppendUint64(timeKey(at), seq)
		return b.Put(key, value)
	})
}

// query calls f with each value in bucket stored between start and end,
// inclusive, in time order; a nil start is the first value, and a nil end
// the last. If neither is given, f is only called with the most recent value.
// Values are only valid during f. It fails with NotFound if nothing was ever
// stored in bucket.
func (v *Vehicle) query(bucket string, start, end *timestamppb.Timestamp, f func([]byte) error) error {
	for _, t := range []*timestamppb.Timestamp{start, end} {
		if t != nil {
			if err := t.CheckValid(); err != nil {
				return status.Error(codes.InvalidArgument, err.Error())
			}
		}
	}
	if start != nil && end != nil && end.AsTime().Before(start.AsTime()) {
		return status.Error(codes.InvalidArgument, "end time is before start time")
	}

	err := v.db.View(func(tx *bolt.Tx) error {
		b := tx.Bucket([]byte(bucket))
		if b == nil {
			return status.Errorf(codes.NotFound, "nothing stored for %q", bucket)
		}
		c := b.Cursor()
		if start == nil && end == nil {
			if _, value := c.Last(); value != nil {
				return f(value)
			}
			return nil
		}
		key, value := c.First()
		if start != nil {
			key, value = c.Seek(timeKey(start.AsTime()))
		}
		var last []byte
		if end != nil {
			last = timeKey(end.AsTime())
		}
		for ; key != nil; key, value = c.Next() {
			if last != nil && bytes.Compare(key[:8], last) > 0 {
				break
			}
			if err := f(value); err != nil {
				return err
			}
		}
		return nil
	})
	if _, ok := status.FromError(err); !ok {
		err = status.Error(codes.Internal, err.Error())
	}
	return err
}

// timeKey builds a timestamp key for the datastore.
func timeKey(t time.Time) []byte {
	key := make([]byte, 8)
	binary.BigEndian.PutUint64(key, uint64(max(t.UnixNano(), 0)))
	return key
}
