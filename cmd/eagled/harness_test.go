package main_test

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"testing"
	"time"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

var (
	eagledBinary     string
	mockDriverBinary string
	mockAviaryBinary string
)

// TestMain builds the real eagled binary and the fixture driver once for every
// test in this package, matching core/util's own mocks/go pattern for building
// plugin fixtures.
func TestMain(m *testing.M) {
	dir, err := os.MkdirTemp("", "eagled-blackbox-*")
	if err != nil {
		panic(err)
	}
	defer os.RemoveAll(dir)

	eagledBinary = filepath.Join(dir, "eagled")
	if out, err := exec.Command("go", "build", "-o", eagledBinary, ".").CombinedOutput(); err != nil {
		panic(fmt.Sprintf("building eagled: %v\n%s", err, out))
	}

	mockDriverBinary = filepath.Join(dir, "mockdriver")
	if out, err := exec.Command("go", "build", "-o", mockDriverBinary, "./testdata/mockdriver").CombinedOutput(); err != nil {
		panic(fmt.Sprintf("building mockdriver: %v\n%s", err, out))
	}

	mockAviaryBinary = filepath.Join(dir, "mockaviary")
	if out, err := exec.Command("go", "build", "-o", mockAviaryBinary, "./testdata/mockaviary").CombinedOutput(); err != nil {
		panic(fmt.Sprintf("building mockaviary: %v\n%s", err, out))
	}

	os.Exit(m.Run())
}

// freePort asks the OS for a currently-unused TCP port on 127.0.0.1.
func freePort(t *testing.T) int {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("finding a free port: %v", err)
	}
	defer ln.Close()
	return ln.Addr().(*net.TCPAddr).Port
}

// writeMockDriver stages the fixture driver under
// dataDir/steeleagle/plugins/driver/<name>, matching
// util.GetInstalledPluginDir("driver").
func writeMockDriver(t *testing.T, dataDir, name string) {
	t.Helper()
	dir := filepath.Join(dataDir, "steeleagle", "plugins", "driver", name)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("creating driver dir: %v", err)
	}
	data, err := os.ReadFile(mockDriverBinary)
	if err != nil {
		t.Fatalf("reading mock driver binary: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "binary"), data, 0755); err != nil {
		t.Fatalf("staging mock driver binary: %v", err)
	}
	runSh := "#!/bin/sh\nexec ./binary\n"
	if err := os.WriteFile(filepath.Join(dir, "run.sh"), []byte(runSh), 0755); err != nil {
		t.Fatalf("staging mock driver run.sh: %v", err)
	}
}

// eagledInstance is a running eagled subprocess and a client dialed to its
// DaemonService.
type eagledInstance struct {
	Client      eagledpb.DaemonServiceClient
	DataDir     string
	PluginDir   string
	ControlPort int

	cmd    *exec.Cmd
	exited chan struct{} // closed once cmd.Wait() returns
}

// WaitExit blocks until the eagled process has actually exited, failing the
// test if it doesn't within timeout. Needed before starting a second instance
// against the same persisted state, so the first one has actually released its
// ports.
func (inst *eagledInstance) WaitExit(t *testing.T, timeout time.Duration) {
	t.Helper()
	select {
	case <-inst.exited:
	case <-time.After(timeout):
		t.Fatalf("eagled did not exit within %s", timeout)
	}
}

// startEagled launches eagled as a real subprocess with an isolated data
// directory and control port, and waits for its DaemonService to accept
// connections. It's torn down via t.Cleanup.
func startEagled(t *testing.T, dataDir string) *eagledInstance {
	t.Helper()

	if dataDir == "" {
		dataDir = t.TempDir()
	}
	pluginDir := t.TempDir()
	controlPort := freePort(t)

	cmd := exec.Command(eagledBinary, "-control-port", fmt.Sprintf("%d", controlPort))
	cmd.Env = append(os.Environ(),
		"XDG_DATA_HOME="+dataDir,
		"XDG_RUNTIME_DIR="+t.TempDir(),
		"TS_AUTHKEY=",
		"TS_VEHICLE_AUTHKEY=",
	)
	cmd.Stdout = testWriter{t}
	cmd.Stderr = testWriter{t}
	if err := cmd.Start(); err != nil {
		t.Fatalf("starting eagled: %v", err)
	}

	exited := make(chan struct{})
	go func() {
		cmd.Wait()
		close(exited)
	}()

	t.Cleanup(func() {
		select {
		case <-exited:
			return
		default:
		}
		cmd.Process.Signal(syscall.SIGTERM)
		select {
		case <-exited:
		case <-time.After(10 * time.Second):
			cmd.Process.Kill()
			<-exited
		}
	})

	addr := fmt.Sprintf("127.0.0.1:%d", controlPort)
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatalf("dialing eagled: %v", err)
	}
	t.Cleanup(func() { conn.Close() })

	client := eagledpb.NewDaemonServiceClient(conn)
	waitForReady(t, client)

	return &eagledInstance{
		Client:      client,
		DataDir:     dataDir,
		PluginDir:   pluginDir,
		ControlPort: controlPort,
		cmd:         cmd,
		exited:      exited,
	}
}

// waitForReady polls GetStatus until eagled's DaemonService actually accepts
// connections.
func waitForReady(t *testing.T, client eagledpb.DaemonServiceClient) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	var lastErr error
	for time.Now().Before(deadline) {
		ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
		_, err := client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
		cancel()
		if err == nil {
			return
		}
		lastErr = err
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("eagled never became ready: %v", lastErr)
}

// baseConfig is a minimal, offline config document with one vehicle bound to
// the mock driver.
func baseConfig(inst *eagledInstance, vehiclePort int, vehicleName, driverName string) string {
	return fmt.Sprintf(`
port-base = %d
plugin-dir = %q
hostname = "test-daemon"

[backend.swarm-controller]
address = "127.0.0.1:1"

[[vehicles]]
name = %q
[vehicles.driver]
name = %q
`, vehiclePort, inst.PluginDir, vehicleName, driverName)
}

// testWriter adapts *testing.T into an io.Writer, so a subprocess's output
// lands in the test log instead of being lost or interleaving on stdout.
type testWriter struct{ t *testing.T }

func (w testWriter) Write(p []byte) (int, error) {
	w.t.Logf("%s", p)
	return len(p), nil
}
