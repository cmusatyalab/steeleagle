package control

import (
	"bytes"
	"context"
	"encoding/json"
	"net"
	"net/http"
	"net/http/httptest"
	"slices"
	"sync"
	"testing"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
	"google.golang.org/protobuf/proto"
)

// received is a call the fake daemon received.
type received struct {
	vehicle string // its route key
	method  string
	req     proto.Message
}

// fakeDaemon stands in for the daemon routing calls to vehicles. Calls to the
// vehicles in fail fail, and calls to the vehicles in block wait until their
// context is done.
type fakeDaemon struct {
	driverpb.UnimplementedControlServiceServer
	missionpb.UnimplementedMissionServiceServer
	fail  map[string]bool
	block map[string]bool

	mu    sync.Mutex
	calls []received
}

func (d *fakeDaemon) record(ctx context.Context, method string, req proto.Message) error {
	md, _ := metadata.FromIncomingContext(ctx)
	keys := md.Get(routeHeader)
	if len(keys) != 1 {
		return status.Errorf(codes.InvalidArgument, "got route keys %v, want one", keys)
	}
	d.mu.Lock()
	d.calls = append(d.calls, received{keys[0], method, req})
	d.mu.Unlock()
	if d.block[keys[0]] {
		<-ctx.Done()
		return status.FromContextError(ctx.Err()).Err()
	}
	if d.fail[keys[0]] {
		return status.Errorf(codes.PermissionDenied, "%s is not allowed", method)
	}
	return nil
}

// received returns the calls received so far, sorted by vehicle and stably
// in the order each vehicle received them.
func (d *fakeDaemon) received() []received {
	d.mu.Lock()
	defer d.mu.Unlock()
	calls := slices.Clone(d.calls)
	slices.SortStableFunc(calls, func(a, b received) int {
		if a.vehicle < b.vehicle {
			return -1
		} else if a.vehicle > b.vehicle {
			return 1
		}
		return 0
	})
	return calls
}

func (d *fakeDaemon) TakeOff(ctx context.Context, req *driverpb.TakeOffRequest) (*driverpb.TakeOffResponse, error) {
	return &driverpb.TakeOffResponse{}, d.record(ctx, "TakeOff", req)
}

func (d *fakeDaemon) Land(ctx context.Context, req *driverpb.LandRequest) (*driverpb.LandResponse, error) {
	return &driverpb.LandResponse{}, d.record(ctx, "Land", req)
}

func (d *fakeDaemon) ReturnToHome(ctx context.Context, req *driverpb.ReturnToHomeRequest) (*driverpb.ReturnToHomeResponse, error) {
	return &driverpb.ReturnToHomeResponse{}, d.record(ctx, "ReturnToHome", req)
}

func (d *fakeDaemon) Hold(ctx context.Context, req *driverpb.HoldRequest) (*driverpb.HoldResponse, error) {
	return &driverpb.HoldResponse{}, d.record(ctx, "Hold", req)
}

func (d *fakeDaemon) SetVelocityTarget(ctx context.Context, req *driverpb.SetVelocityTargetRequest) (*driverpb.SetVelocityTargetResponse, error) {
	return &driverpb.SetVelocityTargetResponse{}, d.record(ctx, "SetVelocityTarget", req)
}

func (d *fakeDaemon) SetGimbalAngleTarget(ctx context.Context, req *driverpb.SetGimbalAngleTargetRequest) (*driverpb.SetGimbalAngleTargetResponse, error) {
	return &driverpb.SetGimbalAngleTargetResponse{}, d.record(ctx, "SetGimbalAngleTarget", req)
}

func (d *fakeDaemon) StartMission(ctx context.Context, req *missionpb.StartMissionRequest) (*missionpb.StartMissionResponse, error) {
	return &missionpb.StartMissionResponse{}, d.record(ctx, "StartMission", req)
}

func (d *fakeDaemon) StopMission(ctx context.Context, req *missionpb.StopMissionRequest) (*missionpb.StopMissionResponse, error) {
	return &missionpb.StopMissionResponse{}, d.record(ctx, "StopMission", req)
}

// serve serves the fake daemon d, and returns a server for a controller
// calling it with timeout.
func serve(t *testing.T, d *fakeDaemon, timeout time.Duration) *httptest.Server {
	t.Helper()
	ln := bufconn.Listen(1 << 20)
	server := grpc.NewServer()
	driverpb.RegisterControlServiceServer(server, d)
	missionpb.RegisterMissionServiceServer(server, d)
	go server.Serve(ln)
	t.Cleanup(server.Stop)
	conn, err := grpc.NewClient("passthrough:///daemon",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) { return ln.DialContext(ctx) }),
		grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return serveController(t, New(conn, timeout, zerolog.Nop()))
}

func serveController(t *testing.T, c *Controller) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/start", c.ServeStart)
	mux.HandleFunc("POST /api/command", c.ServeCommand)
	mux.HandleFunc("POST /api/joystick", c.ServeJoystick)
	mux.HandleFunc("POST /api/gimbal", c.ServeGimbal)
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

// post posts body as JSON to path, returning the status and the decoded
// response.
func post(t *testing.T, server *httptest.Server, path, body string) (int, Response, string) {
	t.Helper()
	resp, err := http.Post(server.URL+path, "application/json", bytes.NewBufferString(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var raw json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		t.Fatalf("POST %s: response isn't JSON: %v", path, err)
	}
	var out Response
	var detail struct{ Detail string }
	json.Unmarshal(raw, &out)
	json.Unmarshal(raw, &detail)
	return resp.StatusCode, out, detail.Detail
}

// methods returns the vehicle and method of each call.
func methods(calls []received) [][2]string {
	var out [][2]string
	for _, c := range calls {
		out = append(out, [2]string{c.vehicle, c.method})
	}
	return out
}

// TestCommands ensures that each endpoint makes its calls on every vehicle,
// routed to the vehicle, with the request's values.
func TestCommands(t *testing.T) {
	for _, tc := range []struct {
		path, body string
		calls      []string // per vehicle, in order
		check      func(t *testing.T, req proto.Message)
	}{
		{"/api/start", `{"vehicles": ["a", "b"]}`, []string{"StartMission"}, nil},
		{"/api/command", `{"takeoff": 12, "vehicles": ["a", "b"]}`, []string{"TakeOff"},
			func(t *testing.T, req proto.Message) {
				if got := req.(*driverpb.TakeOffRequest).GetAltitude(); got != 12 {
					t.Errorf("take off altitude = %v, want 12", got)
				}
			}},
		{"/api/command", `{"land": true, "vehicles": ["a", "b"]}`, []string{"Land"}, nil},
		{"/api/command", `{"rth": true, "vehicles": ["a", "b"]}`, []string{"ReturnToHome"}, nil},
		{"/api/command", `{"hold": true, "vehicles": ["a", "b"]}`, []string{"Hold", "StopMission"}, nil},
		{"/api/command", `{"stop_mission": true, "vehicles": ["a", "b"]}`, []string{"StopMission"}, nil},
		{"/api/joystick", `{"xvel": 1, "yvel": -2, "zvel": 0.5, "angularvel": 30, "duration": 1, "vehicles": ["a", "b"]}`,
			[]string{"SetVelocityTarget"}, func(t *testing.T, req proto.Message) {
				v := req.(*driverpb.SetVelocityTargetRequest).GetVelocity()
				if v.GetXVel() != 1 || v.GetYVel() != -2 || v.GetZVel() != 0.5 || v.GetAngularVel() != 30 {
					t.Errorf("velocity = %v, want the joystick's", v)
				}
				if !v.HasZVel() {
					t.Error("velocity leaves out z, want every axis set")
				}
			}},
		{"/api/gimbal", `{"pitch": 5, "yaw": -3, "vehicles": ["a", "b"]}`, []string{"SetGimbalAngleTarget"},
			func(t *testing.T, req proto.Message) {
				r := req.(*driverpb.SetGimbalAngleTargetRequest)
				if p := r.GetPose(); p.GetPitch() != 5 || p.GetYaw() != -3 || p.GetRoll() != 0 {
					t.Errorf("pose = %v, want the request's", p)
				}
				if r.GetAngleMode() != driverpb.AngleMode_ANGLE_MODE_OFFSET {
					t.Errorf("angle mode = %v, want an offset", r.GetAngleMode())
				}
			}},
	} {
		t.Run(tc.path+" "+tc.body, func(t *testing.T) {
			d := &fakeDaemon{}
			server := serve(t, d, DefaultTimeout)
			code, resp, detail := post(t, server, tc.path, tc.body)
			if code != http.StatusOK {
				t.Fatalf("status %d (%s), want %d", code, detail, http.StatusOK)
			}
			var want [][2]string
			var wantResults []Result
			for _, vehicle := range []string{"a", "b"} {
				for _, m := range tc.calls {
					want = append(want, [2]string{vehicle, m})
					wantResults = append(wantResults, Result{Vehicle: vehicle, Command: m, Success: true})
				}
			}
			calls := d.received()
			if got := methods(calls); !slices.Equal(got, want) {
				t.Errorf("daemon received %v, want %v", got, want)
			}
			if !slices.Equal(resp.Results, wantResults) {
				t.Errorf("results = %+v, want %+v", resp.Results, wantResults)
			}
			if tc.check != nil {
				for _, c := range calls {
					tc.check(t, c.req)
				}
			}
		})
	}
}

// TestCommandFailures ensures that a vehicle whose call fails is reported
// without failing the others, and that a hold still stops the mission of a
// vehicle that can't hold.
func TestCommandFailures(t *testing.T) {
	d := &fakeDaemon{fail: map[string]bool{"b": true}}
	server := serve(t, d, DefaultTimeout)
	code, resp, _ := post(t, server, "/api/command", `{"hold": true, "vehicles": ["a", "b"]}`)
	if code != http.StatusOK {
		t.Fatalf("status %d, want %d", code, http.StatusOK)
	}
	want := []Result{
		{Vehicle: "a", Command: "Hold", Success: true},
		{Vehicle: "a", Command: "StopMission", Success: true},
		{Vehicle: "b", Command: "Hold", Details: "Hold is not allowed"},
		{Vehicle: "b", Command: "StopMission", Details: "StopMission is not allowed"},
	}
	if !slices.Equal(resp.Results, want) {
		t.Errorf("results = %+v, want %+v", resp.Results, want)
	}
}

// TestCommandsConcurrent ensures that a vehicle that doesn't answer doesn't
// hold up the others, and times out.
func TestCommandsConcurrent(t *testing.T) {
	d := &fakeDaemon{block: map[string]bool{"slow": true}}
	server := serve(t, d, 300*time.Millisecond)
	start := time.Now()
	code, resp, _ := post(t, server, "/api/command", `{"land": true, "vehicles": ["slow", "a", "b"]}`)
	if code != http.StatusOK {
		t.Fatalf("status %d, want %d", code, http.StatusOK)
	}
	if elapsed := time.Since(start); elapsed > 2*time.Second {
		t.Errorf("took %v, want about one timeout", elapsed)
	}
	if len(resp.Results) != 3 || resp.Results[0].Vehicle != "slow" || resp.Results[0].Success {
		t.Fatalf("results = %+v, want slow to time out first", resp.Results)
	}
	for _, r := range resp.Results[1:] {
		if !r.Success {
			t.Errorf("result %+v, want success", r)
		}
	}
}

func TestInvalidRequests(t *testing.T) {
	d := &fakeDaemon{}
	server := serve(t, d, DefaultTimeout)
	for _, tc := range []struct{ path, body string }{
		{"/api/start", `{"vehicles": []}`},
		{"/api/start", `{}`},
		{"/api/start", `{"vehicles": [""]}`},
		{"/api/start", `not json`},
		{"/api/command", `{"vehicles": ["a"]}`},
		{"/api/command", `{"land": true, "rth": true, "vehicles": ["a"]}`},
		{"/api/command", `{"takeoff": -1, "vehicles": ["a"]}`},
		{"/api/command", `{"arm": true, "vehicles": ["a"]}`},
		{"/api/joystick", `{"xvel": "fast", "vehicles": ["a"]}`},
	} {
		code, _, detail := post(t, server, tc.path, tc.body)
		if code != http.StatusBadRequest || detail == "" {
			t.Errorf("POST %s %s = %d %q, want %d with a detail", tc.path, tc.body, code, detail, http.StatusBadRequest)
		}
	}
	if calls := d.received(); len(calls) != 0 {
		t.Errorf("daemon received %v for invalid requests, want nothing", methods(calls))
	}
}

// TestDuplicateVehicles ensures that a vehicle named twice is sent its
// command once.
func TestDuplicateVehicles(t *testing.T) {
	d := &fakeDaemon{}
	server := serve(t, d, DefaultTimeout)
	if code, resp, _ := post(t, server, "/api/command", `{"land": true, "vehicles": ["a", "a"]}`); code != http.StatusOK || len(resp.Results) != 1 {
		t.Errorf("got %d %+v, want one result", code, resp.Results)
	}
	if calls := d.received(); len(calls) != 1 {
		t.Errorf("daemon received %v, want one call", methods(calls))
	}
}

// TestFalseCommand ensures that a command set to false sends nothing.
func TestFalseCommand(t *testing.T) {
	d := &fakeDaemon{}
	server := serve(t, d, DefaultTimeout)
	if code, resp, _ := post(t, server, "/api/command", `{"land": false, "vehicles": ["a"]}`); code != http.StatusOK || len(resp.Results) != 0 {
		t.Errorf("got %d %+v, want no results", code, resp.Results)
	}
	if calls := d.received(); len(calls) != 0 {
		t.Errorf("daemon received %v, want nothing", methods(calls))
	}
}

// TestWithoutDaemon ensures that a GCS without a daemon connection says so.
func TestWithoutDaemon(t *testing.T) {
	server := serveController(t, New(nil, DefaultTimeout, zerolog.Nop()))
	if code, _, detail := post(t, server, "/api/start", `{"vehicles": ["a"]}`); code != http.StatusServiceUnavailable || detail == "" {
		t.Errorf("got %d %q, want %d with a detail", code, detail, http.StatusServiceUnavailable)
	}
}
