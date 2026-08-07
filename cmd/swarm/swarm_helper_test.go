package main_test

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"testing"
	"time"

	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

var swarmBinary string

// TestMain builds the real swarm binary once for every test in this package.
func TestMain(m *testing.M) {
	dir, err := os.MkdirTemp("", "swarm-blackbox-*")
	if err != nil {
		panic(err)
	}
	defer os.RemoveAll(dir)

	swarmBinary = filepath.Join(dir, "swarm")
	if out, err := exec.Command("go", "build", "-o", swarmBinary, ".").CombinedOutput(); err != nil {
		panic(fmt.Sprintf("building swarm: %v\n%s", err, out))
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

// swarmInstance is a running swarm subprocess.
type swarmInstance struct {
	Registry    swarmpb.RegistryServiceClient
	Swarm       swarmpb.SwarmServiceClient
	ListenPort  int
	VehiclePort int

	cmd    *exec.Cmd
	exited chan struct{} // closed once cmd.Wait() returns
}

// startSwarm launches swarm as a real subprocess in plain mode (no tsnet) with
// isolated ports, and waits for both services to accept connections.  It's
// torn down via t.Cleanup.
func startSwarm(t *testing.T) *swarmInstance {
	t.Helper()

	listenPort := freePort(t)
	vehiclePort := freePort(t)

	configPath := filepath.Join(t.TempDir(), "config.toml")
	config := fmt.Sprintf(`
listen-port = %d
swarm-listen = "plain"
vehicle-port = %d
registry-listen = "plain"
call-timeout = "2s"
`, listenPort, vehiclePort)
	if err := os.WriteFile(configPath, []byte(config), 0644); err != nil {
		t.Fatalf("writing config: %v", err)
	}

	cmd := exec.Command(swarmBinary, "-config", configPath)
	cmd.Stdout = testWriter{t}
	cmd.Stderr = testWriter{t}
	if err := cmd.Start(); err != nil {
		t.Fatalf("starting swarm: %v", err)
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

	registryConn := waitForReady(t, vehiclePort)
	swarmConn := waitForReady(t, listenPort)

	return &swarmInstance{
		Registry:    swarmpb.NewRegistryServiceClient(registryConn),
		Swarm:       swarmpb.NewSwarmServiceClient(swarmConn),
		ListenPort:  listenPort,
		VehiclePort: vehiclePort,
		cmd:         cmd,
		exited:      exited,
	}
}

// waitForReady dials 127.0.0.1:port until the listener actually accepts
// connections, then returns a gRPC client connection to it.
func waitForReady(t *testing.T, port int) *grpc.ClientConn {
	t.Helper()
	addr := fmt.Sprintf("127.0.0.1:%d", port)
	deadline := time.Now().Add(5 * time.Second)
	var lastErr error
	for time.Now().Before(deadline) {
		conn, err := net.DialTimeout("tcp", addr, 200*time.Millisecond)
		if err == nil {
			conn.Close()
			break
		}
		lastErr = err
		time.Sleep(50 * time.Millisecond)
	}
	if time.Now().After(deadline) {
		t.Fatalf("swarm never became ready on %s: %v", addr, lastErr)
	}

	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatalf("dialing %s: %v", addr, err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

// testWriter adapts *testing.T into an io.Writer, so a subprocess's output
// lands in the test log.
type testWriter struct{ t *testing.T }

func (w testWriter) Write(p []byte) (int, error) {
	w.t.Logf("%s", p)
	return len(p), nil
}
