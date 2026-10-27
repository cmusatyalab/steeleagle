package vehicle

import (
	"bytes"
	"context"
	"encoding/binary"
	"os"
	"path/filepath"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	uriel "github.com/cmusatyalab/uriel/go"
	"go.etcd.io/bbolt"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// openDatastore starts the vehicle datastore, and starts recording results
// and telemetry from the driver and flow engines.
func (v *Vehicle) openDatastore() error {
	dir, err := util.GetVehicleDataDirByName(v.Name)
	if err != nil {
		v.log.Error().Err(err).Msg("failed to open vehicle data directory")
		return err
	}
	os.Remove(filepath.Join(dir, DataDbName)) // clear previous datastore, if it exists
	v.db, err = bbolt.Open(filepath.Join(dir, DataDbName), 0600, &bbolt.Options{Timeout: time.Second})
	if err != nil {
		v.log.Error().Err(err).Msg("failed to open datastore")
		return err
	}
	// Uriel handles are created one at a time, and all exist once this
	// returns: creating them concurrently can briefly change the process umask
	// (see helper_test.go), and nothing published after this is missed
	ready := make(chan struct{})
	v.dataWg.Add(1)
	go v.storeTelemetry(v.ctx, v.streamInfo.telemetry, ready)
	<-ready
	for _, p := range append([]string{v.streamInfo.telemetry}, v.streamInfo.cameras...) {
		v.dataWg.Add(1)
		go v.storeProducerResults(v.ctx, p, ready)
		<-ready
	}
	return nil
}

// store writes value to bucket under time at. Keys are the time in Unix
// nanoseconds followed by a sequence number, both big endian, so that they
// sort by time and never collide.
func (v *Vehicle) store(bucket string, at time.Time, value []byte) error {
	return v.db.Update(func(tx *bbolt.Tx) error {
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
// inclusive, in time order from oldest to newest.
func (v *Vehicle) query(bucket string, start, end time.Time, f func([]byte) error) error {
	err := v.db.View(func(tx *bbolt.Tx) error {
		b := tx.Bucket([]byte(bucket))
		if b == nil {
			return status.Errorf(codes.NotFound, "nothing stored for %q", bucket)
		}
		c := b.Cursor()
		if start.IsZero() && end.IsZero() {
			if _, value := c.Last(); value != nil {
				return f(value)
			}
			return nil
		}
		key, value := c.First()
		if !start.IsZero() {
			key, value = c.Seek(timeKey(start))
		}
		var last []byte
		if !end.IsZero() {
			last = timeKey(end)
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

// storeTelemetry stores the telemetry the driver publishes on `producer` until
// ctx is done. ready is signaled once its reader is created.
func (v *Vehicle) storeTelemetry(ctx context.Context, producer string, ready chan<- struct{}) {
	defer v.dataWg.Done()
	reader, err := uriel.NewReader(producer)
	ready <- struct{}{}
	if err != nil {
		v.log.Error().Err(err).Str("producer", producer).Msg("failed to subscribe to telemetry")
		return // this shouldn't happen
	}
	// A reader must be closed on the goroutine that created it
	defer reader.Close()
	for {
		input, err := reader.Next(ctx)
		if ctx.Err() != nil {
			return
		} else if err != nil {
			v.log.Error().Err(err).Str("producer", producer).Msg("failed to read telemetry")
			continue
		}
		if err := v.store(TelemetryBucket, time.Now(), input.Data); err != nil {
			v.log.Error().Err(err).Msg("could not store telemetry")
		}
	}
}

// storeProducerResults stores the results that come back for `producer` until
// ctx is done. ready is signaled once its subscription is created.
func (v *Vehicle) storeProducerResults(ctx context.Context, producer string, ready chan<- struct{}) {
	defer v.dataWg.Done()
	sub, err := uriel.SubscribeProducer(producer)
	ready <- struct{}{}
	if err != nil {
		v.log.Error().Err(err).Str("producer", producer).Msg("failed to subscribe to producer")
		return // this shouldn't happen
	}
	// A subscriber must be closed on the goroutine that created it
	defer sub.Close()
	for {
		event, err := sub.Next(ctx)
		if ctx.Err() != nil {
			return
		} else if err != nil {
			v.log.Error().Err(err).Str("producer", producer).Msg("failed to read producer event")
			continue
		}
		v.flowInfo.mu.Lock()
		current := event.Flow == v.flowInfo.name
		v.flowInfo.mu.Unlock()
		if event.Kind != uriel.EventResult || !current || event.Engine == "" || len(event.Result) == 0 {
			continue
		}
		t := time.Now()
		bytes, err := v.getResult(event, t)
		if err != nil {
			v.log.Error().Err(err).Str("producer", producer).Msg("couldn't marshal result, skipping")
			continue
		}
		if err := v.store(event.Engine, t, bytes); err != nil {
			v.log.Error().Err(err).Str("producer", producer).Msg("couldn't store result")
		}
	}
}

// getResult returns a compute result proto wrapped around the given result marshalled
// into bytes. Results from unknown engines, or of a type without its own field in
// ComputeResult, are wrapped as generic results.
func (v *Vehicle) getResult(event uriel.Event, at time.Time) ([]byte, error) {
	builder := resultpb.ComputeResult_builder{Timestamp: timestamppb.New(at)}
	output := GenericResultType
	if e, ok := v.engines[event.Engine]; ok {
		if e.Config != nil && e.Config.Engine != nil {
			output = e.Config.Engine.Result
		}
		builder.Local = e.Local
	}
	var err error
	switch output {
	case DetectionResultType:
		builder.DetectionResult = &resultpb.DetectionResult{}
		err = proto.Unmarshal(event.Result, builder.DetectionResult)
	case ClassificationResultType:
		builder.ClassificationResult = &resultpb.ClassificationResult{}
		err = proto.Unmarshal(event.Result, builder.ClassificationResult)
	case GuidanceResultType:
		builder.GuidanceResult = &resultpb.GuidanceResult{}
		err = proto.Unmarshal(event.Result, builder.GuidanceResult)
	case PositionResultType:
		builder.PositionResult = &resultpb.PositionResult{}
		err = proto.Unmarshal(event.Result, builder.PositionResult)
	default:
		builder.GenericResult = resultpb.GenericResult_builder{Payload: event.Result}.Build()
	}
	if err != nil {
		return nil, err
	}
	return proto.Marshal(builder.Build())
}

// timeKey builds a timestamp key for the datastore.
func timeKey(t time.Time) []byte {
	key := make([]byte, 8)
	binary.BigEndian.PutUint64(key, uint64(max(t.UnixNano(), 0)))
	return key
}
