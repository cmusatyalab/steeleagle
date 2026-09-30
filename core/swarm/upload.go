package swarm

import (
	"bytes"
	"context"
	"crypto/sha256"
	"io"
	"sync"
	"sync/atomic"
	"time"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	// uploadChunkSize is the chunk size used toward vehicles.
	uploadChunkSize = 256 * 1024
	// maxMissionSize bounds each uploaded variant.
	maxMissionSize = 128 << 20
	// maxMissionVariants bounds how many variants a single header may declare,
	// so a malformed header can't make the controller reserve unbounded memory.
	maxMissionVariants = 4

	defaultUploadIdleTimeout = 30 * time.Second
	defaultUploadMaxDuration = 5 * time.Minute
	defaultProgressInterval  = time.Second
)

// missionVariant is one architecture's fully received mission binary.
type missionVariant struct {
	header *missionpb.MissionHeader
	data   []byte
}

type uploadStream = grpc.BidiStreamingServer[swarmpb.SwarmUploadMissionRequest, swarmpb.SwarmUploadMissionResponse]

// SwarmUploadMission receives and validates a complete multi-arch mission
// upload, then streams each targeted vehicle the variant matching its
// architecture concurrently, relaying throttled progress and exactly one
// final result per vehicle. A malformed upload fails the whole RPC before
// any vehicle is contacted.
func (s *SwarmServer) SwarmUploadMission(stream uploadStream) error {
	vehicles, variants, err := receiveUpload(stream)
	if err != nil {
		return err
	}

	ctx := stream.Context()
	events := make(chan *swarmpb.SwarmUploadMissionResponse)
	var wg sync.WaitGroup
	for _, vehicle := range vehicles {
		wg.Add(1)
		go func() {
			defer wg.Done()
			s.uploadToVehicle(ctx, vehicle, variants, events)
		}()
	}
	go func() {
		wg.Wait()
		close(events)
	}()

	for ev := range events {
		if err := stream.Send(ev); err != nil {
			for range events { // unblock the per-vehicle goroutines; ctx is cancelled with the client
			}
			return err
		}
	}
	return nil
}

// receiveUpload reads the header and every chunk, returning the de-duplicated
// vehicle list and each variant's verified bytes.
func receiveUpload(stream uploadStream) ([]string, map[string]*missionVariant, error) {
	first, err := stream.Recv()
	if err == io.EOF {
		return nil, nil, status.Error(codes.InvalidArgument, "upload stream was empty; the first message must be a header")
	}
	if err != nil {
		return nil, nil, err
	}
	if !first.HasHeader() {
		return nil, nil, status.Error(codes.InvalidArgument, "the first upload message must be a header")
	}
	header := first.GetHeader()
	vehicles := dedupe(header.GetVehicles())
	if len(vehicles) == 0 {
		return nil, nil, status.Error(codes.InvalidArgument, "no target vehicles")
	}
	if len(header.GetVariants()) > maxMissionVariants {
		return nil, nil, status.Errorf(codes.InvalidArgument, "too many mission variants: %d exceeds the maximum of %d", len(header.GetVariants()), maxMissionVariants)
	}
	variants := make(map[string]*missionVariant)
	for _, mh := range header.GetVariants() {
		arch := mh.GetArch()
		switch {
		case arch == "":
			return nil, nil, status.Error(codes.InvalidArgument, "variant arch must be set")
		case variants[arch] != nil:
			return nil, nil, status.Errorf(codes.InvalidArgument, "duplicate %s variant", arch)
		case mh.GetSize() == 0 || mh.GetSize() > maxMissionSize:
			return nil, nil, status.Errorf(codes.InvalidArgument, "%s variant size %d must be between 1 and %d bytes", arch, mh.GetSize(), maxMissionSize)
		case len(mh.GetSha256()) != sha256.Size:
			return nil, nil, status.Errorf(codes.InvalidArgument, "%s variant sha256 must be %d bytes", arch, sha256.Size)
		}
		variants[arch] = &missionVariant{header: mh}
	}
	if len(variants) == 0 {
		return nil, nil, status.Error(codes.InvalidArgument, "no mission variants")
	}

	for {
		msg, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, nil, err
		}
		if !msg.HasChunk() {
			return nil, nil, status.Error(codes.InvalidArgument, "only the first upload message may be a header")
		}
		chunk := msg.GetChunk()
		v := variants[chunk.GetArch()]
		if v == nil {
			return nil, nil, status.Errorf(codes.InvalidArgument, "chunk for undeclared %q variant", chunk.GetArch())
		}
		if uint64(len(v.data)+len(chunk.GetData())) > v.header.GetSize() {
			return nil, nil, status.Errorf(codes.InvalidArgument, "%s variant exceeds its declared %d bytes", chunk.GetArch(), v.header.GetSize())
		}
		v.data = append(v.data, chunk.GetData()...)
	}

	for arch, v := range variants {
		if uint64(len(v.data)) != v.header.GetSize() {
			return nil, nil, status.Errorf(codes.InvalidArgument, "%s variant: received %d bytes, header declared %d", arch, len(v.data), v.header.GetSize())
		}
		sum := sha256.Sum256(v.data)
		if !bytes.Equal(sum[:], v.header.GetSha256()) {
			return nil, nil, status.Errorf(codes.InvalidArgument, "%s variant: sha256 mismatch", arch)
		}
	}
	return vehicles, variants, nil
}

// uploadToVehicle runs one vehicle's upload and reports its final result.
func (s *SwarmServer) uploadToVehicle(ctx context.Context, vehicle string, variants map[string]*missionVariant, events chan<- *swarmpb.SwarmUploadMissionResponse) {
	err := s.sendMission(ctx, vehicle, variants, func(sent, total uint64) {
		events <- swarmpb.SwarmUploadMissionResponse_builder{
			Vehicle:  vehicle,
			Progress: swarmpb.UploadProgress_builder{Sent: sent, Total: total}.Build(),
		}.Build()
	})
	log := s.logger()
	if err != nil {
		log.Warn().Str("vehicle", vehicle).Str("rpc", "SwarmUploadMission").Err(err).Msg("mission upload failed")
	} else {
		log.Info().Str("vehicle", vehicle).Str("rpc", "SwarmUploadMission").Msg("mission uploaded")
	}
	code, details := statusOf(err)
	b := swarmpb.SwarmUploadMissionResponse_builder{Vehicle: vehicle, Code: code, Details: details}
	if err == nil {
		b.Response = &missionpb.UploadMissionResponse{}
	}
	events <- b.Build()
}

// sendMission picks the variant for vehicle's architecture and streams it,
// failing the vehicle if no chunk is accepted for uploadIdleTimeout.
func (s *SwarmServer) sendMission(ctx context.Context, vehicle string, variants map[string]*missionVariant, progress func(sent, total uint64)) error {
	conn, err := s.clientConn(vehicle)
	if err != nil {
		return err
	}
	client := missionpb.NewMissionServiceClient(conn)

	infoCtx, cancelInfo := context.WithTimeout(ctx, s.callTimeout())
	info, err := client.GetMissionInfo(infoCtx, &missionpb.GetMissionInfoRequest{})
	cancelInfo()
	if err != nil {
		if status.Code(err) == codes.Unimplemented {
			return status.Errorf(codes.Unimplemented, "vehicle's mission service does not support uploads (missing or outdated missionservice): %s", status.Convert(err).Message())
		}
		return err
	}
	v := variants[info.GetArch()]
	if v == nil {
		return status.Errorf(codes.FailedPrecondition, "no %s variant provided", info.GetArch())
	}

	upCtx, cancelUp := context.WithTimeout(ctx, s.uploadMaxDuration)
	defer cancelUp()
	idle := newIdleWatchdog(s.uploadIdleTimeout, cancelUp)
	defer idle.stop()

	up, err := client.UploadMission(upCtx)
	if err != nil {
		if hardCapExceeded(upCtx, idle) {
			return status.Errorf(codes.DeadlineExceeded, "upload did not finish within %s", s.uploadMaxDuration)
		}
		return err
	}
	total := v.header.GetSize()
	// Pause the watchdog around progress(): time spent blocked on a slow
	// events consumer (e.g. GCS client back-pressure) must never count
	// against the idle window, and kicking only after progress() returns
	// can't undo a firing that happened while still blocked inside it.
	idle.stop()
	progress(0, total)
	idle.kick()
	if err := up.Send(missionpb.UploadMissionRequest_builder{Header: v.header}.Build()); err == nil {
		idle.kick()
		last := time.Now()
		for off := 0; off < len(v.data); off += uploadChunkSize {
			end := min(off+uploadChunkSize, len(v.data))
			if err := up.Send(missionpb.UploadMissionRequest_builder{Chunk: v.data[off:end]}.Build()); err != nil {
				break // CloseAndRecv below reports the real status
			}
			idle.kick()
			if sent := uint64(end); sent == total || time.Since(last) >= s.progressInterval {
				idle.stop()
				progress(sent, total)
				idle.kick()
				last = time.Now()
			}
		}
	}
	// The idle watchdog only covers the Send loop above: once every chunk has
	// been handed to gRPC, the vehicle's post-EOF commit (sha256 check,
	// fsync, rename) is bounded by uploadMaxDuration alone, not by
	// uploadIdleTimeout, so a slow-but-honest commit isn't mistaken for a
	// stalled upload.
	idle.stop()
	_, err = up.CloseAndRecv()
	if err != nil && idle.fired.Load() {
		return status.Errorf(codes.DeadlineExceeded, "no upload progress for %s", s.uploadIdleTimeout)
	}
	if err != nil && hardCapExceeded(upCtx, idle) {
		return status.Errorf(codes.DeadlineExceeded, "upload did not finish within %s", s.uploadMaxDuration)
	}
	return err
}

// hardCapExceeded reports whether upCtx's own deadline (uploadMaxDuration)
// expired without the idle watchdog having fired first -- i.e. the vehicle
// kept making progress, but the whole upload simply ran too long.
func hardCapExceeded(upCtx context.Context, idle *idleWatchdog) bool {
	return upCtx.Err() == context.DeadlineExceeded && !idle.fired.Load()
}

// idleWatchdog calls onIdle if kick isn't called within timeout.
type idleWatchdog struct {
	timeout time.Duration
	timer   *time.Timer
	fired   atomic.Bool
}

func newIdleWatchdog(timeout time.Duration, onIdle func()) *idleWatchdog {
	w := &idleWatchdog{timeout: timeout}
	w.timer = time.AfterFunc(timeout, func() {
		w.fired.Store(true)
		onIdle()
	})
	return w
}

func (w *idleWatchdog) kick() { w.timer.Reset(w.timeout) }
func (w *idleWatchdog) stop() { w.timer.Stop() }

// dedupe returns names with each value kept once, in first-occurrence order.
func dedupe(names []string) []string {
	seen := make(map[string]bool, len(names))
	out := make([]string, 0, len(names))
	for _, n := range names {
		if !seen[n] {
			seen[n] = true
			out = append(out, n)
		}
	}
	return out
}
