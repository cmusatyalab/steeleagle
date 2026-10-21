package vehicle

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"sync/atomic"
	"testing"
	"time"

	"github.com/adrg/xdg"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// fakeDriver is a driver plugin that runs until its context is canceled or
// exit is called, and takes a while to clean up, like a real plugin process.
type fakeDriver struct {
	running  atomic.Bool
	startErr error
	done     chan struct{}
	exit     chan error
	exitErr  error
}

func (f *fakeDriver) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	if !f.running.CompareAndSwap(false, true) {
		return nil, nil, fmt.Errorf("plugin already running")
	}
	if f.startErr != nil {
		f.running.Store(false)
		return nil, nil, f.startErr
	}
	conn, err := grpc.NewClient("passthrough:///driver",
		grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		f.running.Store(false)
		return nil, nil, err
	}
	f.done, f.exit = make(chan struct{}), make(chan error, 1)
	done, exit := f.done, f.exit
	go func() {
		select {
		case <-ctx.Done():
			f.exitErr = ctx.Err()
		case f.exitErr = <-exit:
		}
		time.Sleep(50 * time.Millisecond)
		conn.Close()
		f.running.Store(false)
		close(done)
	}()
	return nil, conn, nil
}

func (f *fakeDriver) Watch() <-chan error {
	ch := make(chan error, 1)
	go func() { ch <- f.Wait() }()
	return ch
}

func (f *fakeDriver) Wait() error {
	<-f.done
	return f.exitErr
}

func (f *fakeDriver) Name() string            { return "fake" }
func (f *fakeDriver) Code() listener.AuthCode { return listener.AdminCode }
func (f *fakeDriver) Running() bool           { return f.running.Load() }

// newTestVehicle creates a vehicle with a fake driver, using temporary XDG
// directories.
func newTestVehicle(t *testing.T) (*Vehicle, *fakeDriver) {
	t.Helper()
	t.Setenv("XDG_RUNTIME_DIR", t.TempDir())
	t.Setenv("XDG_DATA_HOME", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)
	driver := &fakeDriver{}
	cfg := &config.PluginConfig{
		Plugin: config.PluginRoot{Name: "fake", Type: "driver"},
		Driver: &config.DriverCap{},
	}
	v, err := NewVehicle(driver, cfg, WithName("test"), WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatal(err)
	}
	return v, driver
}

// waitTimeout calls Wait, failing the test if the vehicle doesn't stop in time.
func waitTimeout(t *testing.T, v *Vehicle) error {
	t.Helper()
	ch := make(chan error, 1)
	go func() { ch <- v.Wait() }()
	select {
	case err := <-ch:
		return err
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for vehicle to stop")
		return nil
	}
}

// TestRestart ensures that a stopped vehicle can be started again right away,
// and that each run cleans up its runtime directory.
func TestRestart(t *testing.T) {
	v, _ := newTestVehicle(t)
	if err := v.Wait(); err == nil {
		t.Error("expected Wait to fail before the vehicle is started")
	}
	for i := range 3 {
		ctx, cancel := context.WithCancel(context.Background())
		daemonLn := listener.NewLocalListener(listener.AdminCode)
		if err := v.Start(ctx, daemonLn); err != nil {
			t.Fatalf("start %d failed: %v", i, err)
		}
		if err := v.Start(ctx, nil); err == nil {
			t.Errorf("start %d: expected a second Start to fail while running", i)
		}
		// The daemon reaches the vehicle through its listener for this run
		conn, err := daemonLn.Dial(ctx, "")
		if err != nil {
			t.Errorf("run %d: couldn't dial daemon listener: %v", i, err)
		} else {
			conn.Close()
		}
		cancel()
		if err := waitTimeout(t, v); err != nil {
			t.Errorf("run %d: expected no error after cancel, got %v", i, err)
		}
		if v.Running.Load() {
			t.Errorf("run %d: expected vehicle to not be running", i)
		}
		if _, err := os.Stat(v.RunDir); !os.IsNotExist(err) {
			t.Errorf("run %d: expected runtime directory to be removed, got %v", i, err)
		}
		if _, err := daemonLn.Dial(context.Background(), ""); err == nil {
			t.Errorf("run %d: expected daemon listener closed after stop", i)
		}
	}
}

// TestRestartAfterDriverExit ensures that a driver exit error is reported by
// Wait, and is cleared by the next run.
func TestRestartAfterDriverExit(t *testing.T) {
	v, driver := newTestVehicle(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := v.Start(ctx, nil); err != nil {
		t.Fatal(err)
	}
	crash := errors.New("crash")
	driver.exit <- crash
	if err := waitTimeout(t, v); !errors.Is(err, crash) {
		t.Errorf("expected driver exit error, got %v", err)
	}
	// Wait keeps reporting the error of the stopped run
	if err := v.Wait(); !errors.Is(err, crash) {
		t.Errorf("expected driver exit error again, got %v", err)
	}

	if err := v.Start(ctx, nil); err != nil {
		t.Fatalf("restart failed: %v", err)
	}
	cancel()
	if err := waitTimeout(t, v); err != nil {
		t.Errorf("expected no error from the restarted run, got %v", err)
	}
}

// TestStartFailure ensures that a failed Start releases what it acquired, so
// that the vehicle can be started once the failure is fixed.
func TestStartFailure(t *testing.T) {
	v, driver := newTestVehicle(t)
	driver.startErr = errors.New("no driver")
	if err := v.Start(context.Background(), nil); err == nil {
		t.Fatal("expected Start to fail")
	}
	if v.Running.Load() {
		t.Error("expected vehicle to not be running after a failed start")
	}
	if _, err := os.Stat(v.RunDir); !os.IsNotExist(err) {
		t.Errorf("expected runtime directory to be removed, got %v", err)
	}

	driver.startErr = nil
	ctx, cancel := context.WithCancel(context.Background())
	if err := v.Start(ctx, nil); err != nil {
		t.Fatalf("start after failure failed: %v", err)
	}
	cancel()
	if err := waitTimeout(t, v); err != nil {
		t.Errorf("expected no error after cancel, got %v", err)
	}
}
