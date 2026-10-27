package vehicle

import (
	"context"
	"errors"
	"os"
	"sync"
	"testing"
	"time"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/peer"
)

// waitTimeout calls Wait, failing the test if the vehicle doesn't stop in time.
func waitTimeout(t *testing.T, v *Vehicle) error {
	t.Helper()
	ch := make(chan error, 1)
	go func() { ch <- v.Wait() }()
	select {
	case err := <-ch:
		return err
	case <-time.After(10 * time.Second):
		t.Fatal("timed out waiting for vehicle to stop")
		return nil
	}
}

// TestRestart checks that a vehicle can be stopped and started again, that
// each run releases what it allocated, and that missions persist across runs
// while dataflows don't.
func TestRestart(t *testing.T) {
	v, _ := testVehicle(t)
	if err := v.Wait(); err != nil {
		t.Errorf("Wait before Start = %v, want nil", err)
	}
	for i := range 3 {
		ctx, cancel := context.WithCancel(context.Background())
		ln, conn, err := v.Start(ctx)
		if err != nil {
			cancel()
			t.Fatalf("start %d: %v", i, err)
		}
		if _, _, err := v.Start(ctx); err == nil {
			t.Errorf("start %d: a second Start succeeded while running", i)
		}
		runDir := v.runDir
		if conn != v.conn {
			t.Errorf("start %d: returned conn isn't the vehicle's", i)
		}

		// Each run starts without a dataflow, but with the missions so far
		expectFlow(t, v, nil)
		if missions, _ := getMissions(t, v); len(missions) != i {
			t.Errorf("run %d: %d missions, want %d", i, len(missions), i)
		}
		if err := setDataflow(t, v, flowToml(t, "front")); err != nil {
			t.Fatalf("run %d: %v", i, err)
		}
		if err := upload(t, v, string(rune('a'+i)), "mission"); err != nil {
			t.Fatalf("run %d: %v", i, err)
		}

		cancel()
		if err := waitTimeout(t, v); err != nil {
			t.Errorf("run %d: Wait = %v, want nil after cancel", i, err)
		}
		if v.running.Load() {
			t.Errorf("run %d: vehicle still running", i)
		}
		if _, err := os.Stat(runDir); !os.IsNotExist(err) {
			t.Errorf("run %d: runtime directory left behind (%v)", i, err)
		}
		if _, err := ln.(*listener.LocalListener).Dial(context.Background(), ""); err == nil {
			t.Errorf("run %d: daemon listener still open", i)
		}
	}
}

// TestDriverExit checks that a driver that exits stops the vehicle, that Wait
// reports why, and that the vehicle can be started again.
func TestDriverExit(t *testing.T) {
	v, driver := newTestVehicle(t)
	crash := errors.New("crash")
	driver.exit <- crash
	if err := waitTimeout(t, v); !errors.Is(err, crash) {
		t.Errorf("Wait = %v, want the driver's exit error", err)
	}
	if v.running.Load() {
		t.Error("vehicle still running after its driver exited")
	}
	if _, _, err := v.Start(context.Background()); err != nil {
		t.Fatalf("restart: %v", err)
	}
	expectFlow(t, v, nil)
}

// TestStartFailure checks that a failed Start releases what it allocated, so
// that the vehicle can be started once the failure is fixed.
func TestStartFailure(t *testing.T) {
	v, driver := testVehicle(t)
	driver.startErr = errors.New("no driver")
	if _, _, err := v.Start(context.Background()); err == nil {
		t.Fatal("Start succeeded without a driver")
	}
	if v.running.Load() {
		t.Error("vehicle running after a failed start")
	}
	if err := waitTimeout(t, v); err != nil {
		t.Errorf("Wait = %v after a failed start, want nil", err)
	}
	// The run's Uriel client was released, or a new one couldn't take its name
	driver.startErr = nil
	if _, _, err := v.Start(context.Background()); err != nil {
		t.Fatalf("start after the failure was fixed: %v", err)
	}
	expectFlow(t, v, nil)
}

// TestUpstream checks that calls with another service's routing key go out
// through the daemon listener with the vehicle's auth code, and that calls
// with the vehicle's own key never do.
func TestUpstream(t *testing.T) {
	v, _ := testVehicle(t)
	ln, _, err := v.Start(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	// The daemon relay serves the listener; here, a health service that
	// records the auth code of its callers stands in for it
	var mu sync.Mutex
	var callers []listener.AuthCode
	relay := grpc.NewServer(grpc.UnaryInterceptor(func(
		ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler,
	) (any, error) {
		if p, ok := peer.FromContext(ctx); ok {
			if a, ok := p.Addr.(*listener.Addr); ok {
				mu.Lock()
				callers = append(callers, a.Code)
				mu.Unlock()
			}
		}
		return handler(ctx, req)
	}))
	healthpb.RegisterHealthServer(relay, health.NewServer())
	go relay.Serve(ln)
	t.Cleanup(relay.Stop)

	client := healthpb.NewHealthClient(v.conn)
	resp, err := client.Check(router.Embed(callCtx(t), "other"), &healthpb.HealthCheckRequest{})
	if err != nil || resp.GetStatus() != healthpb.HealthCheckResponse_SERVING {
		t.Fatalf("call to another service got %v, %v, want it served by the daemon", resp, err)
	}
	mu.Lock()
	if len(callers) != 1 || callers[0] != listener.PrivilegedCode {
		t.Errorf("daemon got calls with codes %v, want one with the vehicle's", callers)
	}
	mu.Unlock()

	_, err = client.Check(router.Embed(callCtx(t), v.Name), &healthpb.HealthCheckRequest{})
	expectCode(t, err, codes.Unimplemented)
}

// TestConcurrentCalls checks that the vehicle's services can be called at
// once; run with -race, it checks their shared state is locked.
func TestConcurrentCalls(t *testing.T) {
	v, _ := newTestVehicle(t)
	installMission(t, v, "idle")
	if err := loadMission(t, v, "idle"); err != nil {
		t.Fatal(err)
	}
	loader := vehiclepb.NewLoaderServiceClient(v.conn)
	safety := vehiclepb.NewSafetyServiceClient(v.conn)
	var wg sync.WaitGroup
	for i := range 4 {
		wg.Go(func() {
			// Calls may be refused, since they race; they must not break
			for range 3 {
				startMission(t, v)
				loader.GetMissions(callCtx(t), &vehiclepb.GetMissionsRequest{})
				loader.LoadMission(callCtx(t), vehiclepb.LoadMissionRequest_builder{Name: "idle"}.Build())
				safety.SetDataFailsafeBehavior(callCtx(t), vehiclepb.SetDataFailsafeBehaviorRequest_builder{
					Behavior: vehiclepb.FailsafeBehavior(i%4 + 1),
				}.Build())
				safety.GetFailsafeState(callCtx(t), &vehiclepb.GetFailsafeStateRequest{})
				stopMission(t, v)
			}
		})
	}
	wg.Wait()
	if err := stopMission(t, v); err != nil {
		t.Fatal(err)
	}
	if v.mission.Running() {
		t.Error("mission still running")
	}
}
