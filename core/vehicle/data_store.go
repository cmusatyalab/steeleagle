package vehicle

import (
	"context"
	"encoding/binary"
	"fmt"
	"sync"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/result"
	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	"github.com/rs/zerolog/log"
	"go.etcd.io/bbolt"
	"google.golang.org/protobuf/proto"
)

const (
	dbPath          = "%s-store.db" // database file path
	dbOpenMode      = 0600          // database open mode
	maxBatch        = 100           // max number of telemetry entries before flush
	flushInterval   = time.Second   // flush interval
	telemetryBucket = "telemetry"   // database bucket name for telemetry
)

// dataStore stores data associated with a vehicle, such as sensor data and
// computed results. It runs a goroutine to periodically flush telemetry data
// to disk in a Bolt key/value store.
type dataStore struct {
	latestTelemetry *stream_msg_pb.Telemetry           // latest telemetry
	telMu           *sync.RWMutex                      // telemetry mutex
	latestFrame     *stream_msg_pb.EncodedFrame        // latest frame
	frameMu         *sync.RWMutex                      // frame mutex
	latestResults   map[string]*resultpb.ComputeResult // latest results
	resultsMu       *sync.RWMutex                      // results mutex
	telCh           chan *stream_msg_pb.Telemetry      // telemetry flush channel
	db              *bbolt.DB                          // database
}

// Create a new data store.
func newDataStore(vehicleName string) (*dataStore, error) {
	store := &dataStore{
		telMu:     &sync.RWMutex{},
		frameMu:   &sync.RWMutex{},
		resultsMu: &sync.RWMutex{},
		telCh:     make(chan *stream_msg_pb.Telemetry, 1),
	}
	var err error
	store.db, err = bbolt.Open(fmt.Sprintf(dbPath, vehicleName), dbOpenMode, nil)
	if err != nil {
		return nil, err
	}

	return store, nil
}

// Initialize the data store, launching a goroutine that listens for telemetry
// updates on the specified channel.
func (s *dataStore) init(ctx context.Context) error {
	err := s.db.Update(func(tx *bbolt.Tx) error {
		_, err := tx.CreateBucketIfNotExists([]byte(telemetryBucket))
		return err
	})
	if err != nil {
		return err
	}

	go s.storeTelemetryWorker(ctx)
	return nil
}

// itob converts an unsigned int to its big endian binary representation. Big
// endian representations allow for lexicographic ordering that is exactly
// the same as comparing the corresponding integer representations.
func itob(v uint64) []byte {
	b := make([]byte, 8)
	binary.BigEndian.PutUint64(b, v)
	return b
}

// storeTelemetryWorker listens on the provided channel for telemetry data,
// storing it in the internal database periodically.
func (s *dataStore) storeTelemetryWorker(ctx context.Context) {
	// Store data in the internal database periodically in batches
	batch := make([]*stream_msg_pb.Telemetry, 0, maxBatch)
	ticker := time.NewTicker(flushInterval)
	defer ticker.Stop()

	// Flush to db
	flush := func() {
		if len(batch) == 0 {
			return
		}

		err := s.db.Update(func(tx *bbolt.Tx) error {
			b := tx.Bucket([]byte(telemetryBucket))

			for _, tel := range batch {
				key := itob(uint64(tel.Timestamp.AsTime().UnixNano()))

				telBytes, err := proto.Marshal(tel)
				if err != nil {
					return err
				}
				if err := b.Put(key, telBytes); err != nil {
					return err
				}
			}
			return nil
		})

		if err != nil {
			log.Err(err).Msg("telemetry flush failed")
		}
		batch = batch[:0]
	}
	defer flush()

	// Flush at least once every flushInterval
	for {
		select {
		case <-ticker.C:
			flush()
		case t, ok := <-s.telCh:
			if !ok {
				return
			}
			if len(batch) == cap(batch) {
				flush()
			}
			batch = append(batch, t)
		case <-ctx.Done():
			return
		}
	}
}

// Get the latest telemetry available for the vehicle.
func (s *dataStore) getLatestTelemetry() *stream_msg_pb.Telemetry {
	s.telMu.RLock()
	defer s.telMu.RUnlock()
	return s.latestTelemetry
}

// Get the latest frame available for the vehicle.
func (s *dataStore) getLatestFrame() *stream_msg_pb.EncodedFrame {
	s.frameMu.RLock()
	defer s.frameMu.RUnlock()
	return s.latestFrame
}

// Get the latest compute result available for the given producer.
func (s *dataStore) getLatestResult(producerName string) *resultpb.ComputeResult {
	s.resultsMu.RLock()
	defer s.resultsMu.RUnlock()
	return s.latestResults[producerName]
}

// Add new telemetry to the store.
func (s *dataStore) addTelemetry(tel *stream_msg_pb.Telemetry) {
	s.telMu.Lock()
	s.latestTelemetry = tel
	s.telMu.Unlock()
	s.telCh <- tel
}

// Add a video frame to the store.
func (s *dataStore) addFrame(frame *stream_msg_pb.EncodedFrame) {
	s.frameMu.Lock()
	defer s.frameMu.Unlock()

	s.latestFrame = frame
}

// Add a compute result to the store.
func (s *dataStore) addResult(producerName string, res *resultpb.ComputeResult) {
	s.resultsMu.Lock()
	defer s.resultsMu.Unlock()

	s.latestResults[producerName] = res
}
