package compiler

import (
	"context"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"testing"
	"time"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// configModPath is the module of the config package, which the compiled
// missions are built against from this checkout.
const configModPath = "github.com/cmusatyalab/steeleagle/config"

// fakeVehicle serves a mission the way the vehicle does: it records the
// dataflows the mission sets, failing each with flowErr, and every other
// call the mission makes, which fails as unimplemented.
type fakeVehicle struct {
	vehiclepb.UnimplementedDataServiceServer
	flowErr error
	mu      sync.Mutex
	flows   []string
	calls   []string
	called  chan struct{} // closed on the first call other than SetDataflow
	once    sync.Once
}

func (f *fakeVehicle) SetDataflow(_ context.Context, req *vehiclepb.SetDataflowRequest) (*vehiclepb.SetDataflowResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.flows = append(f.flows, string(req.GetToml()))
	if f.flowErr != nil {
		return nil, f.flowErr
	}
	return &vehiclepb.SetDataflowResponse{}, nil
}

func (f *fakeVehicle) unknown(_ any, stream grpc.ServerStream) error {
	method, _ := grpc.MethodFromServerStream(stream)
	f.mu.Lock()
	f.calls = append(f.calls, method)
	f.mu.Unlock()
	f.once.Do(func() { close(f.called) })
	return status.Error(codes.Unimplemented, "fake vehicle")
}

func (f *fakeVehicle) recorded() (flows, calls []string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]string(nil), f.flows...), append([]string(nil), f.calls...)
}

// runMission starts the mission binary bin as the vehicle's plugin does,
// served by vehicle, and returns a client of its mission service and a
// function that waits for the process to exit, returning its result.
func runMission(t *testing.T, bin string, vehicle *fakeVehicle) (missionpb.MissionServiceClient, func() (error, bool)) {
	t.Helper()
	// Unix socket paths are limited in length, which t.TempDir can exceed
	dir, err := os.MkdirTemp("", "mission")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	vehicleSock, missionSock := filepath.Join(dir, "vehicle.sock"), filepath.Join(dir, "mission.sock")

	ln, err := net.Listen("unix", vehicleSock)
	if err != nil {
		t.Fatal(err)
	}
	server := grpc.NewServer(grpc.UnknownServiceHandler(vehicle.unknown))
	vehiclepb.RegisterDataServiceServer(server, vehicle)
	go server.Serve(ln)
	t.Cleanup(server.Stop)

	cmd := exec.Command(bin)
	cmd.Env = append(os.Environ(), "STEELEAGLE_CLIENT_SOCKET="+vehicleSock, "STEELEAGLE_LISTEN_SOCKET="+missionSock)
	cmd.Stderr = testWriter{t}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	exited := make(chan struct{})
	var exitErr error
	go func() {
		exitErr = cmd.Wait()
		close(exited)
	}()
	t.Cleanup(func() {
		cmd.Process.Kill()
		<-exited
	})
	wait := func() (error, bool) {
		select {
		case <-exited:
			return exitErr, true
		case <-time.After(10 * time.Second):
			return nil, false
		}
	}

	// The vehicle waits for the mission's socket the same way
	deadline := time.Now().Add(10 * time.Second)
	for {
		if _, err := os.Stat(missionSock); err == nil {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("mission never listened on STEELEAGLE_LISTEN_SOCKET")
		}
		time.Sleep(10 * time.Millisecond)
	}
	conn, err := grpc.NewClient("unix://"+missionSock, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return missionpb.NewMissionServiceClient(conn), wait
}

// testWriter logs what is written to it, so the mission's logs show with a
// failing test.
type testWriter struct{ t *testing.T }

func (w testWriter) Write(p []byte) (int, error) {
	w.t.Logf("mission: %s", p)
	return len(p), nil
}

// TestCompiledMissionSetsFlowOnStart compiles a mission with a flow file,
// and checks that the binary waits to be started, sets the embedded flow
// on the vehicle when it is, and exits without running the mission when
// the vehicle rejects the flow.
func TestCompiledMissionSetsFlowOnStart(t *testing.T) {
	skipIfShort(t)
	root, err := filepath.Abs(repoRoot(t))
	if err != nil {
		t.Fatal(err)
	}
	src := modulesStanza(root) +
		"    \"" + configModPath + "\" => \"" + filepath.Join(root, "config") + "\"\n" +
		importsStanza(dslPkgPath, actionsPkg) + testMissionBody
	bin := filepath.Join(t.TempDir(), "mission")
	flow := testFlow
	errs := Compile(FromFile(writeMission(t, t.TempDir(), src)),
		buildtools.WithManifest([]byte(testManifest)), buildtools.WithFlow([]byte(flow)),
		buildtools.WithOutputFile(bin))
	if len(errs) > 0 {
		t.Fatalf("Compile() errors = %v", errs)
	}

	t.Run("accepted", func(t *testing.T) {
		vehicle := &fakeVehicle{called: make(chan struct{})}
		client, _ := runMission(t, bin, vehicle)
		time.Sleep(100 * time.Millisecond)
		if flows, calls := vehicle.recorded(); len(flows) > 0 || len(calls) > 0 {
			t.Fatalf("before StartMission, flows = %q and calls = %q, want none", flows, calls)
		}
		if _, err := client.StartMission(context.Background(), &missionpb.StartMissionRequest{}); err != nil {
			t.Fatalf("StartMission() = %v", err)
		}
		select {
		case <-vehicle.called:
		case <-time.After(10 * time.Second):
			t.Fatal("mission made no calls once started")
		}
		flows, calls := vehicle.recorded()
		if len(flows) != 1 || flows[0] != flow {
			t.Errorf("flows = %q, want [%q]", flows, flow)
		}
		if calls[0] != "/steeleagle_protocol.v1.services.driver.ControlService/TakeOff" {
			t.Errorf("first call = %s, want TakeOff", calls[0])
		}
	})

	t.Run("rejected", func(t *testing.T) {
		vehicle := &fakeVehicle{called: make(chan struct{}), flowErr: status.Error(codes.InvalidArgument, "bad flow")}
		client, wait := runMission(t, bin, vehicle)
		_, err := client.StartMission(context.Background(), &missionpb.StartMissionRequest{})
		if status.Code(err) != codes.InvalidArgument {
			t.Fatalf("StartMission() = %v, want the vehicle's InvalidArgument", err)
		}
		if err, ok := wait(); !ok {
			t.Fatal("mission didn't exit after its flow was rejected")
		} else if err == nil {
			t.Error("mission exited successfully, want a failure")
		}
		if _, calls := vehicle.recorded(); len(calls) > 0 {
			t.Errorf("calls = %q, want none once the flow was rejected", calls)
		}
	})
}
