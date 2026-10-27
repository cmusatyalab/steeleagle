package vehicle

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
	"time"

	"github.com/adrg/xdg"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	uriel "github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	"go.etcd.io/bbolt"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// testEngine is the local engine the test compute service serves.
var testEngine = unique("detector")

// missionBinary is the test mission, built by TestMain from testdata/mission.
var missionBinary string

// umask is the process umask when the tests start. iceoryx2, under Uriel,
// sets the process-wide umask to 0177 while it binds a listener's socket, so
// a directory made meanwhile can't be entered, and listeners bound at once can
// leave it at 0177. The vehicle creates its listeners one at a time, but tests
// also create engines, so each test restores it until iceoryx2 is fixed.
var umask int

func TestMain(m *testing.M) {
	code, err := runTests(m)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		code = 1
	}
	os.Exit(code)
}

// runTests sets up isolated XDG directories, builds the test mission,
// shortens the dead man's switch, and runs the tests.
func runTests(m *testing.M) (int, error) {
	// The base is kept short, since plugin sockets are made under it
	base, err := os.MkdirTemp("", "sev")
	if err != nil {
		return 0, err
	}
	defer os.RemoveAll(base)
	for env, dir := range map[string]string{
		"XDG_DATA_HOME":   "d",
		"XDG_CONFIG_HOME": "c",
		"XDG_RUNTIME_DIR": "r",
	} {
		os.Setenv(env, filepath.Join(base, dir))
	}
	xdg.Reload()
	umask = syscall.Umask(0)
	syscall.Umask(umask)

	missionBinary = filepath.Join(base, "mission")
	cmd := exec.Command("go", "build", "-o", missionBinary, "./testdata/mission")
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if out, err := cmd.CombinedOutput(); err != nil {
		return 0, fmt.Errorf("couldn't build test mission: %v\n%s", err, out)
	}

	DmsTimeout = 200 * time.Millisecond
	return m.Run(), nil
}

var names atomic.Uint64

// unique returns a name no other test uses, in this process or another, since
// Uriel names are shared by every process on the machine.
func unique(base string) string {
	return fmt.Sprintf("%s-%d-%d", base, os.Getpid(), names.Add(1))
}

// testLogger returns a logger that only logs when tests are verbose.
func testLogger() zerolog.Logger {
	if testing.Verbose() {
		return zerolog.New(os.Stdout).With().Timestamp().Logger()
	}
	return zerolog.Nop()
}

// testOutput returns stdout when tests are verbose, and discards output
// otherwise.
func testOutput() io.Writer {
	if testing.Verbose() {
		return os.Stdout
	}
	return io.Discard
}

// fakeDriver is a driver plugin, served in process, that records the streams
// and control calls it is asked for. It runs until its context is canceled or
// exit is called, and can be started again after it stops.
type fakeDriver struct {
	driverpb.UnimplementedStreamServiceServer
	driverpb.UnimplementedControlServiceServer
	startErr  error       // error Start fails with, if any
	running   atomic.Bool // whether the driver is running
	exit      chan error  // exits the current run with an error
	run       *fakeRun    // the current or last run
	mu        sync.Mutex
	cameras   []*driverpb.StreamCamerasRequest
	telemetry []string
	holds     int
}

func (f *fakeDriver) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	if f.startErr != nil {
		return nil, nil, f.startErr
	}
	if !f.running.CompareAndSwap(false, true) {
		return nil, nil, errors.New("driver already running")
	}
	ln := listener.NewLocalListener(listener.AdminCode)
	server := grpc.NewServer()
	driverpb.RegisterStreamServiceServer(server, f)
	driverpb.RegisterControlServiceServer(server, f)
	go server.Serve(ln)
	conn, err := grpc.NewClient("passthrough:///driver",
		grpc.WithContextDialer(ln.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		server.Stop()
		f.running.Store(false)
		return nil, nil, err
	}
	run := &fakeRun{done: make(chan struct{})}
	f.exit, f.run = make(chan error, 1), run
	exit := f.exit
	go func() {
		select {
		case <-ctx.Done():
		case run.err = <-exit:
		}
		server.Stop()
		f.running.Store(false)
		close(run.done)
	}()
	return nil, conn, nil
}

// fakeRun is a run of a fake driver. Watch and Wait are about the run that is
// current when they are called, like a plugin's.
type fakeRun struct {
	done chan struct{} // closed when the run stops
	err  error         // exit error of the run
}

func (f *fakeDriver) Watch() <-chan error {
	ch := make(chan error, 1)
	run := f.run
	go func() { ch <- run.wait() }()
	return ch
}

func (f *fakeDriver) Wait() error {
	return f.run.wait()
}

func (r *fakeRun) wait() error {
	if r == nil {
		return nil
	}
	<-r.done
	return r.err
}

func (f *fakeDriver) Name() string            { return "fake" }
func (f *fakeDriver) Code() listener.AuthCode { return listener.AdminCode }
func (f *fakeDriver) Running() bool           { return f.running.Load() }

func (f *fakeDriver) StreamCameras(
	ctx context.Context,
	req *driverpb.StreamCamerasRequest,
) (*driverpb.StreamCamerasResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.cameras = append(f.cameras, req)
	return &driverpb.StreamCamerasResponse{}, nil
}

func (f *fakeDriver) StreamTelemetry(
	ctx context.Context,
	req *driverpb.StreamTelemetryRequest,
) (*driverpb.StreamTelemetryResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.telemetry = append(f.telemetry, req.GetUri())
	return &driverpb.StreamTelemetryResponse{}, nil
}

func (f *fakeDriver) Hold(ctx context.Context, req *driverpb.HoldRequest) (*driverpb.HoldResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.holds++
	return &driverpb.HoldResponse{}, nil
}

func (f *fakeDriver) SetVelocityTarget(
	ctx context.Context,
	req *driverpb.SetVelocityTargetRequest,
) (*driverpb.SetVelocityTargetResponse, error) {
	return &driverpb.SetVelocityTargetResponse{}, nil
}

func (f *fakeDriver) SetGimbalVelocityTarget(
	ctx context.Context,
	req *driverpb.SetGimbalVelocityTargetRequest,
) (*driverpb.SetGimbalVelocityTargetResponse, error) {
	return &driverpb.SetGimbalVelocityTargetResponse{}, nil
}

// cameraRequests returns the camera streams asked for so far.
func (f *fakeDriver) cameraRequests() []*driverpb.StreamCamerasRequest {
	f.mu.Lock()
	defer f.mu.Unlock()
	return slices.Clone(f.cameras)
}

// holdCount returns how many times the driver was told to hold.
func (f *fakeDriver) holdCount() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.holds
}

// testCameras are the cameras of the test driver: "front" and "rear" are
// both primary, "down" is not.
var testCameras = []config.DriverCamera{
	{Name: "front", Primary: true},
	{Name: "rear", Primary: true},
	{Name: "down"},
}

// testDriverConfig is the config of the test driver, which streams
// testCameras.
func testDriverConfig() *config.PluginConfig {
	return &config.PluginConfig{
		Plugin: config.PluginRoot{Name: "fake", Type: "driver"},
		Driver: &config.DriverCap{
			Cameras: testCameras,
			Supported: config.DriverSupported{Services: []string{
				"steeleagle_protocol/v1/services/driver/StreamService",
				"steeleagle_protocol/v1/services/driver/ControlService",
			}},
		},
	}
}

// testVehicle is a vehicle that isn't started, wrapping a fake driver that
// streams testCameras. Its local compute service is a Uriel server serving
// testEngine, a detection engine.
func testVehicle(t *testing.T) (*Vehicle, *fakeDriver) {
	t.Helper()
	syscall.Umask(umask)
	lcs := unique("lcs")
	server, err := uriel.NewServer(lcs)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { server.Close() })
	if err := server.AddEngine(testEngine); err != nil {
		t.Fatal(err)
	}
	engines := EngineMap{testEngine: {
		Config: &config.PluginConfig{Engine: &config.EngineCap{Result: DetectionResultType}},
		Local:  true,
	}}
	driver := &fakeDriver{}
	v, err := NewVehicle(driver, testDriverConfig(),
		WithName(unique("vehicle")),
		WithAuthCode(listener.PrivilegedCode),
		WithMissionDir(t.TempDir()),
		WithLogger(testLogger()),
		WithLocalCompute(lcs, engines),
	)
	if err != nil {
		t.Fatal(err)
	}
	// The vehicle stops before the compute service does
	t.Cleanup(func() {
		if v.cancel != nil {
			v.cancel()
		}
		v.Wait()
	})
	return v, driver
}

// newTestVehicle returns a running vehicle from testVehicle, whose services
// are reached through v.conn, as the daemon reaches them.
func newTestVehicle(t *testing.T) (*Vehicle, *fakeDriver) {
	t.Helper()
	v, driver := testVehicle(t)
	if _, _, err := v.Start(context.Background()); err != nil {
		t.Fatal(err)
	}
	return v, driver
}

// waitStored waits until bucket holds n values.
func waitStored(t *testing.T, v *Vehicle, bucket string, n int) {
	t.Helper()
	eventually(t, 5*time.Second, func() error {
		stored := 0
		v.db.View(func(tx *bbolt.Tx) error {
			if b := tx.Bucket([]byte(bucket)); b != nil {
				stored = b.Stats().KeyN
			}
			return nil
		})
		if stored < n {
			return fmt.Errorf("bucket %q holds %d values, want %d", bucket, stored, n)
		}
		return nil
	})
}

// eventually calls f until it returns nil, failing the test with its last
// error if it doesn't within timeout.
func eventually(t *testing.T, timeout time.Duration, f func() error) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for {
		err := f()
		if err == nil {
			return
		}
		if time.Now().After(deadline) {
			t.Fatalf("condition not met after %v: %v", timeout, err)
		}
		time.Sleep(20 * time.Millisecond)
	}
}

// expectCode fails the test unless err is a status error with code, whose
// message contains each of contains.
func expectCode(t *testing.T, err error, code codes.Code, contains ...string) {
	t.Helper()
	if status.Code(err) != code {
		t.Fatalf("got error %v, want code %v", err, code)
	}
	for _, c := range contains {
		if !strings.Contains(status.Convert(err).Message(), c) {
			t.Errorf("error %q doesn't mention %q", status.Convert(err).Message(), c)
		}
	}
}

// callCtx returns a context for a call that fails the test rather than hangs.
func callCtx(t *testing.T) context.Context {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	t.Cleanup(cancel)
	return ctx
}
