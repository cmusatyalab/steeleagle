package fsm

import (
	"context"
	"errors"
	"net"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// fakeDataService records the dataflows set on it, failing each with err.
type fakeDataService struct {
	vehiclepb.UnimplementedDataServiceServer
	mu    sync.Mutex
	flows [][]byte
	err   error
}

func (f *fakeDataService) SetDataflow(_ context.Context, req *vehiclepb.SetDataflowRequest) (*vehiclepb.SetDataflowResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.flows = append(f.flows, req.GetToml())
	if f.err != nil {
		return nil, f.err
	}
	return &vehiclepb.SetDataflowResponse{}, nil
}

func (f *fakeDataService) setFlows() [][]byte {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([][]byte(nil), f.flows...)
}

// serveHarness runs Serve with a mission of the single action execute, and
// a vehicle serving data. It returns a client of the mission service and
// Serve's result, once it returns.
type serveHarness struct {
	client missionpb.MissionServiceClient
	result chan error
	cancel context.CancelFunc
}

func newServeHarness(t *testing.T, flowToml []byte, data *fakeDataService, execute func(sdk.Vehicle) error) *serveHarness {
	t.Helper()
	// Unix socket paths are limited in length, which t.TempDir can exceed
	dir, err := os.MkdirTemp("", "fsm")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })

	vehicleLn, err := net.Listen("unix", filepath.Join(dir, "vehicle.sock"))
	if err != nil {
		t.Fatal(err)
	}
	vehicle := grpc.NewServer()
	vehiclepb.RegisterDataServiceServer(vehicle, data)
	go vehicle.Serve(vehicleLn)
	t.Cleanup(vehicle.Stop)
	conn, err := grpc.NewClient("unix://"+vehicleLn.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })

	missionSock := filepath.Join(dir, "mission.sock")
	ln, err := net.Listen("unix", missionSock)
	if err != nil {
		t.Fatal(err)
	}
	newMission := func() *DslFsm {
		actions := map[string]dsl.Action{"a": &fakeAction{execute: execute}}
		return NewDslFsm("a", nil, actions, nil, dsl.MissionData{Log: zerolog.Nop()}, conn)
	}
	ctx, cancel := context.WithCancel(context.Background())
	h := &serveHarness{result: make(chan error, 1), cancel: cancel}
	go func() { h.result <- Serve(ctx, ln, conn, flowToml, zerolog.Nop(), newMission) }()
	t.Cleanup(func() {
		cancel()
		h.wait(t)
	})

	missionConn, err := grpc.NewClient("unix://"+missionSock, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { missionConn.Close() })
	h.client = missionpb.NewMissionServiceClient(missionConn)
	return h
}

// wait returns Serve's result, failing the test if it doesn't return.
func (h *serveHarness) wait(t *testing.T) error {
	t.Helper()
	select {
	case err := <-h.result:
		h.result <- err // so later waits see it too
		return err
	case <-time.After(5 * time.Second):
		t.Fatal("Serve didn't return")
		return nil
	}
}

// requireRunning fails the test unless Serve is still running.
func (h *serveHarness) requireRunning(t *testing.T) {
	t.Helper()
	select {
	case err := <-h.result:
		t.Fatalf("Serve returned %v, want it still running", err)
	case <-time.After(50 * time.Millisecond):
	}
}

func (h *serveHarness) start(t *testing.T) error {
	t.Helper()
	_, err := h.client.StartMission(context.Background(), &missionpb.StartMissionRequest{})
	return err
}

func (h *serveHarness) stop(t *testing.T) {
	t.Helper()
	if _, err := h.client.StopMission(context.Background(), &missionpb.StopMissionRequest{}); err != nil {
		t.Fatalf("StopMission() = %v", err)
	}
}

// TestServeWaitsForStart checks that the mission only runs once it is
// started, and that Serve returns nil once it completes.
func TestServeWaitsForStart(t *testing.T) {
	ran := make(chan struct{})
	h := newServeHarness(t, nil, &fakeDataService{}, func(sdk.Vehicle) error { close(ran); return nil })

	select {
	case <-ran:
		t.Fatal("mission ran before StartMission")
	case <-time.After(50 * time.Millisecond):
	}
	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() = %v", err)
	}
	if err := h.wait(t); err != nil {
		t.Fatalf("Serve() = %v, want nil once the mission completes", err)
	}
	<-ran
}

// TestServeSetsFlowOnStart checks that each start sets the mission's
// dataflow before the mission runs.
func TestServeSetsFlowOnStart(t *testing.T) {
	data := &fakeDataService{}
	flow := []byte("[[producers]]\nname = \"front\"\n")
	var flowsAtRun [][]byte
	h := newServeHarness(t, flow, data, func(v sdk.Vehicle) error {
		flowsAtRun = data.setFlows()
		<-v.Ctx().Done()
		return v.Ctx().Err()
	})

	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() = %v", err)
	}
	h.stop(t)
	if len(flowsAtRun) != 1 || string(flowsAtRun[0]) != string(flow) {
		t.Fatalf("flows set when the mission ran = %q, want [%q]", flowsAtRun, flow)
	}
	if err := h.start(t); err != nil {
		t.Fatalf("second StartMission() = %v", err)
	}
	if got := data.setFlows(); len(got) != 2 {
		t.Errorf("flows set after two starts = %q, want 2", got)
	}
}

// TestServeWithoutFlowSetsNone checks that a mission without a dataflow
// doesn't set one.
func TestServeWithoutFlowSetsNone(t *testing.T) {
	data := &fakeDataService{}
	h := newServeHarness(t, nil, data, func(sdk.Vehicle) error { return nil })
	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() = %v", err)
	}
	h.wait(t)
	if got := data.setFlows(); len(got) != 0 {
		t.Errorf("flows set = %q, want none", got)
	}
}

// TestServeExitsWhenFlowFails checks that a dataflow the vehicle rejects
// fails StartMission with the vehicle's error and makes Serve return it,
// without running the mission.
func TestServeExitsWhenFlowFails(t *testing.T) {
	data := &fakeDataService{err: status.Error(codes.InvalidArgument, "bad flow")}
	ran := false
	h := newServeHarness(t, []byte("bad"), data, func(sdk.Vehicle) error { ran = true; return nil })

	err := h.start(t)
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("StartMission() = %v, want the vehicle's InvalidArgument", err)
	}
	if err := h.wait(t); err == nil {
		t.Fatal("Serve() = nil, want the dataflow error")
	}
	if ran {
		t.Error("mission ran although its dataflow couldn't be set")
	}
}

// TestServeStopAndRestart checks that StopMission ends the run without
// ending Serve, and that the mission can then be started again.
func TestServeStopAndRestart(t *testing.T) {
	var mu sync.Mutex
	runs := 0
	h := newServeHarness(t, nil, &fakeDataService{}, func(v sdk.Vehicle) error {
		mu.Lock()
		runs++
		mu.Unlock()
		<-v.Ctx().Done()
		return v.Ctx().Err()
	})

	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() = %v", err)
	}
	h.stop(t)
	h.requireRunning(t)
	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() after stop = %v", err)
	}
	h.stop(t)
	mu.Lock()
	defer mu.Unlock()
	if runs != 2 {
		t.Errorf("runs = %d, want 2", runs)
	}
}

// TestServeStopWithoutRun checks that stopping a mission that isn't running
// succeeds.
func TestServeStopWithoutRun(t *testing.T) {
	h := newServeHarness(t, nil, &fakeDataService{}, func(sdk.Vehicle) error { return nil })
	h.stop(t)
	h.requireRunning(t)
}

// TestServeRejectsSecondStart checks that a mission can't be started while
// it is running.
func TestServeRejectsSecondStart(t *testing.T) {
	h := newServeHarness(t, nil, &fakeDataService{}, func(v sdk.Vehicle) error {
		<-v.Ctx().Done()
		return v.Ctx().Err()
	})
	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() = %v", err)
	}
	if err := h.start(t); status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("second StartMission() = %v, want FailedPrecondition", err)
	}
}

// TestServeReturnsMissionError checks that Serve returns a run's error.
func TestServeReturnsMissionError(t *testing.T) {
	boom := errors.New("boom")
	h := newServeHarness(t, nil, &fakeDataService{}, func(sdk.Vehicle) error { return boom })
	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() = %v", err)
	}
	if err := h.wait(t); !errors.Is(err, boom) {
		t.Fatalf("Serve() = %v, want %v", err, boom)
	}
}

// TestServeCancelStopsRun checks that canceling Serve's context stops the
// running mission, and that Serve then returns nil.
func TestServeCancelStopsRun(t *testing.T) {
	stopped := make(chan struct{})
	h := newServeHarness(t, nil, &fakeDataService{}, func(v sdk.Vehicle) error {
		<-v.Ctx().Done()
		close(stopped)
		return v.Ctx().Err()
	})
	if err := h.start(t); err != nil {
		t.Fatalf("StartMission() = %v", err)
	}
	h.cancel()
	if err := h.wait(t); err != nil {
		t.Fatalf("Serve() = %v, want nil once canceled", err)
	}
	select {
	case <-stopped:
	default:
		t.Error("Serve returned before the run stopped")
	}
}
