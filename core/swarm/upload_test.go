package swarm_test

import (
	"context"
	"crypto/sha256"
	"io"
	"net"
	"net/netip"
	"strings"
	"sync"
	"testing"
	"time"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"github.com/cmusatyalab/steeleagle/core/swarm"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// fakeMissionVehicle is a MissionService fixture recording what it receives.
type fakeMissionVehicle struct {
	missionpb.UnimplementedMissionServiceServer
	arch        string
	infoErr     error         // returned by GetMissionInfo when set
	stall       chan struct{} // when set, UploadMission stops reading after the header until closed or cancelled
	commitDelay time.Duration // when set, UploadMission sleeps this long after the recv loop before SendAndClose

	mu      sync.Mutex
	uploads int
	header  *missionpb.MissionHeader
	data    []byte
	ctxErr  error // the stream context's error once an upload ended early
}

func (v *fakeMissionVehicle) GetMissionInfo(context.Context, *missionpb.GetMissionInfoRequest) (*missionpb.GetMissionInfoResponse, error) {
	if v.infoErr != nil {
		return nil, v.infoErr
	}
	return missionpb.GetMissionInfoResponse_builder{Arch: v.arch}.Build(), nil
}

func (v *fakeMissionVehicle) UploadMission(stream grpc.ClientStreamingServer[missionpb.UploadMissionRequest, missionpb.UploadMissionResponse]) error {
	first, err := stream.Recv()
	if err != nil {
		return err
	}
	v.mu.Lock()
	v.uploads++
	v.header = first.GetHeader()
	v.mu.Unlock()
	if v.stall != nil {
		select {
		case <-v.stall:
		case <-stream.Context().Done():
			v.mu.Lock()
			v.ctxErr = stream.Context().Err()
			v.mu.Unlock()
			return stream.Context().Err()
		}
	}
	for {
		msg, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			v.mu.Lock()
			v.ctxErr = err
			v.mu.Unlock()
			return err
		}
		v.mu.Lock()
		v.data = append(v.data, msg.GetChunk()...)
		v.mu.Unlock()
	}
	if v.commitDelay > 0 {
		time.Sleep(v.commitDelay)
	}
	return stream.SendAndClose(&missionpb.UploadMissionResponse{})
}

func (v *fakeMissionVehicle) snapshot() (uploads int, header *missionpb.MissionHeader, data []byte, ctxErr error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.uploads, v.header, append([]byte{}, v.data...), v.ctxErr
}

// startMissionVehicle serves v on loopback with small fixed flow-control
// windows, so a stalled reader really does block the sender.
func startMissionVehicle(t *testing.T, v *fakeMissionVehicle) netip.AddrPort {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listening for fixture vehicle: %v", err)
	}
	g := grpc.NewServer(grpc.InitialWindowSize(64*1024), grpc.InitialConnWindowSize(64*1024))
	missionpb.RegisterMissionServiceServer(g, v)
	go g.Serve(ln)
	t.Cleanup(g.Stop)
	addr, err := netip.ParseAddrPort(ln.Addr().String())
	if err != nil {
		t.Fatalf("parsing fixture addr: %v", err)
	}
	return addr
}

func payload(n int, seed byte) []byte {
	b := make([]byte, n)
	for i := range b {
		b[i] = seed + byte(i%251)
	}
	return b
}

func variantHeader(arch string, data []byte) *missionpb.MissionHeader {
	sum := sha256.Sum256(data)
	return missionpb.MissionHeader_builder{Arch: arch, Size: uint64(len(data)), Sha256: sum[:]}.Build()
}

// uploadRequests builds a correct header+chunks request sequence.
func uploadRequests(vehicles []string, variants map[string][]byte) []*swarmpb.SwarmUploadMissionRequest {
	header := swarmpb.SwarmUploadMissionHeader_builder{Vehicles: vehicles}.Build()
	var headers []*missionpb.MissionHeader
	for arch, data := range variants {
		headers = append(headers, variantHeader(arch, data))
	}
	header.SetVariants(headers)
	reqs := []*swarmpb.SwarmUploadMissionRequest{swarmpb.SwarmUploadMissionRequest_builder{Header: header}.Build()}
	for arch, data := range variants {
		for off := 0; off < len(data); off += 64 * 1024 {
			end := min(off+64*1024, len(data))
			reqs = append(reqs, swarmpb.SwarmUploadMissionRequest_builder{
				Chunk: swarmpb.SwarmUploadMissionChunk_builder{Arch: arch, Data: data[off:end]}.Build(),
			}.Build())
		}
	}
	return reqs
}

// runUpload sends reqs and collects every response until the stream ends.
func runUpload(t *testing.T, ctx context.Context, client swarmpb.SwarmServiceClient, reqs []*swarmpb.SwarmUploadMissionRequest) ([]*swarmpb.SwarmUploadMissionResponse, error) {
	t.Helper()
	stream, err := client.SwarmUploadMission(ctx)
	if err != nil {
		t.Fatalf("opening SwarmUploadMission: %v", err)
	}
	for _, r := range reqs {
		if err := stream.Send(r); err != nil {
			break
		}
	}
	stream.CloseSend()
	var resps []*swarmpb.SwarmUploadMissionResponse
	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			return resps, nil
		}
		if err != nil {
			return resps, err
		}
		resps = append(resps, resp)
	}
}

// results returns the final (non-progress) responses keyed by vehicle.
func results(resps []*swarmpb.SwarmUploadMissionResponse) map[string]*swarmpb.SwarmUploadMissionResponse {
	out := map[string]*swarmpb.SwarmUploadMissionResponse{}
	for _, r := range resps {
		if !r.HasProgress() {
			out[r.GetVehicle()] = r
		}
	}
	return out
}

func testCtx(t *testing.T) context.Context {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	t.Cleanup(cancel)
	return ctx
}

func TestUpload_RoutesVariantByArch(t *testing.T) {
	amd := &fakeMissionVehicle{arch: "amd64"}
	arm := &fakeMissionVehicle{arch: "arm64"}
	registry := swarm.NewRegistry()
	defer registry.Register("amd", startMissionVehicle(t, amd))()
	defer registry.Register("arm", startMissionVehicle(t, arm))()
	client := startSwarmServer(t, registry)

	amdData, armData := payload(300_000, 1), payload(200_000, 7)
	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"amd", "arm"}, map[string][]byte{"amd64": amdData, "arm64": armData}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	res := results(resps)
	for _, name := range []string{"amd", "arm"} {
		if codes.Code(res[name].GetCode()) != codes.OK {
			t.Fatalf("%s result = %v %q, want OK", name, codes.Code(res[name].GetCode()), res[name].GetDetails())
		}
	}
	if _, h, d, _ := amd.snapshot(); h.GetArch() != "amd64" || string(d) != string(amdData) {
		t.Fatalf("amd64 vehicle got arch %q and %d bytes, want the amd64 variant", h.GetArch(), len(d))
	}
	if _, h, d, _ := arm.snapshot(); h.GetArch() != "arm64" || string(d) != string(armData) {
		t.Fatalf("arm64 vehicle got arch %q and %d bytes, want the arm64 variant", h.GetArch(), len(d))
	}
}

func TestUpload_MissingVariant(t *testing.T) {
	v := &fakeMissionVehicle{arch: "riscv64"}
	registry := swarm.NewRegistry()
	defer registry.Register("harpy", startMissionVehicle(t, v))()
	client := startSwarmServer(t, registry)

	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"harpy"}, map[string][]byte{"amd64": payload(1000, 1)}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	r := results(resps)["harpy"]
	if codes.Code(r.GetCode()) != codes.FailedPrecondition || !strings.Contains(r.GetDetails(), "no riscv64 variant") {
		t.Fatalf("result = %v %q, want FailedPrecondition mentioning riscv64", codes.Code(r.GetCode()), r.GetDetails())
	}
}

func TestUpload_UnknownVehicleAndOldMissionService(t *testing.T) {
	old := &fakeMissionVehicle{arch: "amd64", infoErr: status.Error(codes.Unimplemented, "unknown method GetMissionInfo")}
	registry := swarm.NewRegistry()
	defer registry.Register("old", startMissionVehicle(t, old))()
	client := startSwarmServer(t, registry)

	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"ghost", "old"}, map[string][]byte{"amd64": payload(1000, 1)}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	res := results(resps)
	if codes.Code(res["ghost"].GetCode()) != codes.NotFound {
		t.Fatalf("ghost = %v, want NotFound", codes.Code(res["ghost"].GetCode()))
	}
	if codes.Code(res["old"].GetCode()) != codes.Unimplemented || !strings.Contains(res["old"].GetDetails(), "does not support uploads") {
		t.Fatalf("old = %v %q, want Unimplemented mentioning unsupported uploads", codes.Code(res["old"].GetCode()), res["old"].GetDetails())
	}
}

func TestUpload_ValidationFailsBeforeAnyVehicle(t *testing.T) {
	data := payload(1000, 1)
	good := func() []*swarmpb.SwarmUploadMissionRequest {
		return uploadRequests([]string{"harpy"}, map[string][]byte{"amd64": data})
	}
	cases := map[string]func() []*swarmpb.SwarmUploadMissionRequest{
		"no header": func() []*swarmpb.SwarmUploadMissionRequest { return good()[1:] },
		"no vehicles": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			r[0].GetHeader().SetVehicles(nil)
			return r
		},
		"hash mismatch": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			h := r[0].GetHeader().GetVariants()[0]
			bad := append([]byte{}, h.GetSha256()...)
			bad[0] ^= 0xff
			h.SetSha256(bad)
			return r
		},
		"short": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			return r[:len(r)-1]
		},
		"unknown chunk arch": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			r[1].GetChunk().SetArch("arm64")
			return r
		},
		"duplicate arch": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			vs := r[0].GetHeader().GetVariants()
			r[0].GetHeader().SetVariants(append(vs, vs[0]))
			return r
		},
		"second header": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			return append(r, r[0])
		},
		"variant size zero": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			r[0].GetHeader().GetVariants()[0].SetSize(0)
			return r
		},
		"variant size exceeds max": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			r[0].GetHeader().GetVariants()[0].SetSize(128<<20 + 1)
			return r
		},
		"variant sha256 wrong length": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			h := r[0].GetHeader().GetVariants()[0]
			h.SetSha256(h.GetSha256()[:16])
			return r
		},
		"variant arch empty": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			r[0].GetHeader().GetVariants()[0].SetArch("")
			return r
		},
		"no variants": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			r[0].GetHeader().SetVariants(nil)
			return r
		},
		"too many variants": func() []*swarmpb.SwarmUploadMissionRequest {
			// Every variant is otherwise fully valid (correct size, correct
			// sha256, chunks that add up) so this exercises the variant-count
			// cap itself, not some other validation failure.
			return uploadRequests([]string{"harpy"}, map[string][]byte{
				"v0": payload(10, 0),
				"v1": payload(10, 1),
				"v2": payload(10, 2),
				"v3": payload(10, 3),
				"v4": payload(10, 4),
			})
		},
		"chunk exceeds declared size": func() []*swarmpb.SwarmUploadMissionRequest {
			r := good()
			return append(r, swarmpb.SwarmUploadMissionRequest_builder{
				Chunk: swarmpb.SwarmUploadMissionChunk_builder{Arch: "amd64", Data: []byte{0}}.Build(),
			}.Build())
		},
	}
	for name, build := range cases {
		t.Run(name, func(t *testing.T) {
			v := &fakeMissionVehicle{arch: "amd64"}
			registry := swarm.NewRegistry()
			defer registry.Register("harpy", startMissionVehicle(t, v))()
			client := startSwarmServer(t, registry)

			_, err := runUpload(t, testCtx(t), client, build())
			if status.Code(err) != codes.InvalidArgument {
				t.Fatalf("err = %v, want InvalidArgument", err)
			}
			if uploads, _, _, _ := v.snapshot(); uploads != 0 {
				t.Fatalf("vehicle saw %d uploads, want 0", uploads)
			}
		})
	}
}

func TestUpload_IdleTimeoutAndSlowVehicleIsolation(t *testing.T) {
	stall := make(chan struct{})
	defer close(stall)
	slow := &fakeMissionVehicle{arch: "amd64", stall: stall}
	fast := &fakeMissionVehicle{arch: "amd64"}
	registry := swarm.NewRegistry()
	defer registry.Register("slow", startMissionVehicle(t, slow))()
	defer registry.Register("fast", startMissionVehicle(t, fast))()
	client := startSwarmServer(t, registry, swarm.WithUploadIdleTimeout(1500*time.Millisecond))

	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"slow", "fast"}, map[string][]byte{"amd64": payload(2<<20, 3)}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	var order []string
	for _, r := range resps {
		if !r.HasProgress() {
			order = append(order, r.GetVehicle())
		}
	}
	if len(order) != 2 || order[0] != "fast" {
		t.Fatalf("result order = %v, want fast before slow", order)
	}
	r := results(resps)["slow"]
	if codes.Code(r.GetCode()) != codes.DeadlineExceeded || !strings.Contains(r.GetDetails(), "no upload progress") {
		t.Fatalf("slow = %v %q, want DeadlineExceeded mentioning no upload progress", codes.Code(r.GetCode()), r.GetDetails())
	}
	if codes.Code(results(resps)["fast"].GetCode()) != codes.OK {
		t.Fatalf("fast = %v, want OK", codes.Code(results(resps)["fast"].GetCode()))
	}
}

// TestUpload_SlowCommitDoesNotTripIdleTimeout guards against the idle
// watchdog staying armed through the vehicle's post-EOF commit (sha256
// check, fsync, rename): a vehicle that receives every chunk promptly but
// then takes longer than the idle timeout to reply on UploadMission's
// SendAndClose must still be reported OK, not DeadlineExceeded.
func TestUpload_SlowCommitDoesNotTripIdleTimeout(t *testing.T) {
	v := &fakeMissionVehicle{arch: "amd64", commitDelay: 500 * time.Millisecond}
	registry := swarm.NewRegistry()
	defer registry.Register("harpy", startMissionVehicle(t, v))()
	client := startSwarmServer(t, registry, swarm.WithUploadIdleTimeout(100*time.Millisecond))

	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"harpy"}, map[string][]byte{"amd64": payload(1000, 1)}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	r := results(resps)["harpy"]
	if codes.Code(r.GetCode()) != codes.OK {
		t.Fatalf("result = %v %q, want OK (idle timeout must not cover the vehicle's post-EOF commit)", codes.Code(r.GetCode()), r.GetDetails())
	}
}

// TestUpload_HardCapExceededReportsDeadlineExceeded guards the per-vehicle
// hard cap (uploadMaxDuration): a vehicle that keeps accepting chunks (so the
// idle watchdog never fires) but whose post-EOF commit outlives the hard cap
// must be reported DeadlineExceeded with details naming the hard cap, not a
// bare "context deadline exceeded".
func TestUpload_HardCapExceededReportsDeadlineExceeded(t *testing.T) {
	v := &fakeMissionVehicle{arch: "amd64", commitDelay: 300 * time.Millisecond}
	registry := swarm.NewRegistry()
	defer registry.Register("harpy", startMissionVehicle(t, v))()
	client := startSwarmServer(t, registry,
		swarm.WithUploadMaxDuration(100*time.Millisecond),
		swarm.WithUploadIdleTimeout(10*time.Second), // must not be what fires
	)

	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"harpy"}, map[string][]byte{"amd64": payload(1000, 1)}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	r := results(resps)["harpy"]
	if codes.Code(r.GetCode()) != codes.DeadlineExceeded || !strings.Contains(r.GetDetails(), "upload did not finish within") {
		t.Fatalf("result = %v %q, want DeadlineExceeded mentioning the hard cap", codes.Code(r.GetCode()), r.GetDetails())
	}
}

func TestUpload_ProgressFirstAndLastAlwaysSent(t *testing.T) {
	v := &fakeMissionVehicle{arch: "amd64"}
	registry := swarm.NewRegistry()
	defer registry.Register("harpy", startMissionVehicle(t, v))()
	client := startSwarmServer(t, registry, swarm.WithUploadProgressInterval(time.Hour))

	data := payload(1<<20, 5)
	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"harpy"}, map[string][]byte{"amd64": data}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	if len(resps) != 3 {
		t.Fatalf("got %d responses, want progress(0), progress(total), result", len(resps))
	}
	if p := resps[0].GetProgress(); !resps[0].HasProgress() || p.GetSent() != 0 || p.GetTotal() != uint64(len(data)) {
		t.Fatalf("first = %v, want progress 0/%d", resps[0], len(data))
	}
	if p := resps[1].GetProgress(); !resps[1].HasProgress() || p.GetSent() != uint64(len(data)) {
		t.Fatalf("second = %v, want progress %d/%d", resps[1], len(data), len(data))
	}
	if resps[2].HasProgress() || codes.Code(resps[2].GetCode()) != codes.OK {
		t.Fatalf("third = %v, want OK result", resps[2])
	}
}

func TestUpload_DeduplicatesVehicles(t *testing.T) {
	v := &fakeMissionVehicle{arch: "amd64"}
	registry := swarm.NewRegistry()
	defer registry.Register("harpy", startMissionVehicle(t, v))()
	client := startSwarmServer(t, registry)

	resps, err := runUpload(t, testCtx(t), client, uploadRequests([]string{"harpy", "harpy"}, map[string][]byte{"amd64": payload(1000, 1)}))
	if err != nil {
		t.Fatalf("SwarmUploadMission: %v", err)
	}
	finals := 0
	for _, r := range resps {
		if !r.HasProgress() {
			finals++
		}
	}
	if uploads, _, _, _ := v.snapshot(); finals != 1 || uploads != 1 {
		t.Fatalf("got %d results and %d uploads, want 1 and 1", finals, uploads)
	}
}

func TestUpload_ClientCancelAbortsVehicleUploads(t *testing.T) {
	stall := make(chan struct{})
	defer close(stall)
	v := &fakeMissionVehicle{arch: "amd64", stall: stall}
	registry := swarm.NewRegistry()
	defer registry.Register("harpy", startMissionVehicle(t, v))()
	client := startSwarmServer(t, registry)

	ctx, cancel := context.WithCancel(testCtx(t))
	stream, err := client.SwarmUploadMission(ctx)
	if err != nil {
		t.Fatalf("opening SwarmUploadMission: %v", err)
	}
	for _, r := range uploadRequests([]string{"harpy"}, map[string][]byte{"amd64": payload(2<<20, 9)}) {
		stream.Send(r)
	}
	stream.CloseSend()
	if _, err := stream.Recv(); err != nil { // progress(0): the vehicle upload is under way
		t.Fatalf("waiting for first progress: %v", err)
	}
	cancel()

	deadline := time.After(5 * time.Second)
	for {
		if _, _, _, ctxErr := v.snapshot(); ctxErr != nil {
			return
		}
		select {
		case <-deadline:
			t.Fatal("vehicle upload was never cancelled after the client went away")
		case <-time.After(20 * time.Millisecond):
		}
	}
}
