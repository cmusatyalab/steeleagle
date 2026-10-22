package daemon

import (
	"context"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"io"
	"net"
	"net/netip"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/adrg/xdg"
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/network"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/status"
)

// newTestOrchestrator returns a daemon with a temporary data directory, ready
// to be registered with.
func newTestOrchestrator(t *testing.T) *Daemon {
	t.Helper()
	t.Setenv("XDG_DATA_HOME", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)
	d := &Daemon{
		Config: &config.DaemonConfig{Daemon: config.DaemonRoot{Port: 9000, Lcs: 9001, Hostname: "homebase"}},
		router: router.NewRouter(nil, nil, router.WithLogger(testLogger())),
		log:    testLogger(),
	}
	t.Cleanup(d.closeRemotes)
	return d
}

// TestLcsCert ensures that a cert is generated for the Uriel server name and
// saved with its key, that the saved cert is reused, and that an invalid cert,
// or one for another name, is replaced.
func TestLcsCert(t *testing.T) {
	d := newTestOrchestrator(t)
	first, err := d.lcsCert()
	if err != nil {
		t.Fatalf("generate failed: %v", err)
	}
	block, _ := pem.Decode([]byte(first))
	if block == nil || block.Type != "CERTIFICATE" {
		t.Fatalf("expected a PEM cert and nothing else, got %q", first)
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil || cert.VerifyHostname(lcsServerName) != nil {
		t.Errorf("expected a cert for uriel, got %v, %v", cert, err)
	}
	dir := filepath.Join(xdg.DataHome, "steeleagle", LcsIdentityDirName)
	if info, err := os.Stat(filepath.Join(dir, LcsKeyFileName)); err != nil || info.Mode().Perm() != 0600 {
		t.Errorf("expected key saved with mode 0600, got %v, %v", info, err)
	}

	if again, err := d.lcsCert(); err != nil || again != first {
		t.Errorf("expected saved cert reused, got %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, LcsCertFileName), []byte("garbage"), 0644); err != nil {
		t.Fatal(err)
	}
	replaced, err := d.lcsCert()
	if err != nil || replaced == first {
		t.Errorf("expected invalid cert replaced, got %v", err)
	}

	// A cert for the name Gabriel clients connected with is replaced
	old, _, err := generateCert("gabriel")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, LcsCertFileName), old, 0644); err != nil {
		t.Fatal(err)
	}
	if renamed, err := d.lcsCert(); err != nil || renamed == replaced {
		t.Errorf("expected cert for another name replaced, got %v", err)
	}
}

// yoloToml is the plugin toml of an engine with an engine cap.
const yoloToml = "[plugin]\nname = 'YOLO'\ntype = 'engine'\n\n[engine]\ntype = 'detection'\n" +
	"inputs = ['steeleagle_protocol/v1/messages/frame/RawFrame']\n" +
	"result = 'steeleagle_protocol/v1/messages/result/DetectionResult'\n"

// setTimings shortens the registration timings for a test.
func setTimings(t *testing.T, interval, timeout, backoffMin, backoffMax time.Duration) {
	t.Helper()
	old := []time.Duration{heartbeatInterval, heartbeatTimeout, registerBackoffMin, registerBackoffMax}
	heartbeatInterval, heartbeatTimeout, registerBackoffMin, registerBackoffMax = interval, timeout, backoffMin, backoffMax
	t.Cleanup(func() {
		heartbeatInterval, heartbeatTimeout, registerBackoffMin, registerBackoffMax = old[0], old[1], old[2], old[3]
	})
}

// waitFor waits until cond holds, failing the test after five seconds.
func waitFor(t *testing.T, what string, cond func() bool) {
	t.Helper()
	for deadline := time.Now().Add(5 * time.Second); !cond(); time.Sleep(5 * time.Millisecond) {
		if time.Now().After(deadline) {
			t.Fatalf("timed out waiting for %s", what)
		}
	}
}

// remoteStreams returns the number of open registration streams of the remote
// daemon at ip, or -1 if it isn't registered.
func remoteStreams(d *Daemon, ip string) int {
	d.remotesMu.Lock()
	defer d.remotesMu.Unlock()
	if remote, ok := d.remotes[netip.MustParseAddr(ip)]; ok {
		return remote.streams
	}
	return -1
}

// newRegistrationOrchestrator returns an orchestrator serving engines yolo,
// with an engine cap, and capless, without one, and a client of its relay,
// where every caller is 127.0.0.1.
func newRegistrationOrchestrator(t *testing.T) (*Daemon, daemonpb.DaemonServiceClient) {
	t.Helper()
	t.Setenv("XDG_DATA_HOME", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)
	d, addr := startRoutingDaemon(t, "[daemon]\n")
	d.Config = &config.DaemonConfig{Daemon: config.DaemonRoot{Port: 9000, Lcs: 9001, Hostname: "homebase"}}
	engine := func(name, content string) *serviceInfo {
		cfg, err := config.ParsePluginConfigFromBytes([]byte(content))
		if err != nil {
			t.Fatal(err)
		}
		return &serviceInfo{name: name, category: daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE,
			config: cfg, toml: []byte(content), plugin: &plugin.BasePlugin{}}
	}
	d.services = map[daemonpb.ServiceCategory][]*serviceInfo{
		daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE: {
			engine("100.64.0.1.yolo", yoloToml),
			engine("100.64.0.1.capless", "[plugin]\nname = 'Capless'\ntype = 'engine'\n"),
		},
	}
	t.Cleanup(d.closeRemotes)
	return d, daemonpb.NewDaemonServiceClient(dial(t, addr))
}

// register opens a registration stream on client and sends registration,
// returning the stream and the first response, or the error it fails with.
func register(
	t *testing.T,
	client daemonpb.DaemonServiceClient,
	registration *daemonpb.DaemonRegistration,
) (grpc.BidiStreamingClient[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse], *daemonpb.RegisterOrchestratorResponse, error) {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	stream, err := client.RegisterOrchestrator(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if err := stream.Send(daemonpb.RegisterOrchestratorRequest_builder{Registration: registration}.Build()); err != nil {
		t.Fatal(err)
	}
	resp, err := stream.Recv()
	return stream, resp, err
}

// TestRegisterOrchestrator ensures that a daemon registering its vehicles gets
// the local compute cert and port back, along with the plugin toml of each
// engine with an engine cap, that each heartbeat is answered, that the daemon
// is disconnected, but kept, when its stream ends, and that it can register
// again on another port, replacing its connection.
func TestRegisterOrchestrator(t *testing.T) {
	d, client := newRegistrationOrchestrator(t)
	registration := daemonpb.DaemonRegistration_builder{
		Vehicles: []string{"127.0.0.1.harpy", "127.0.0.1.kestrel"},
		Port:     9100,
	}.Build()
	stream, resp, err := register(t, client, registration)
	if err != nil {
		t.Fatalf("register failed: %v", err)
	}
	compute := resp.GetCompute()
	if compute.GetPort() != 9001 || compute.GetCert() == "" {
		t.Errorf("expected cert and lcs port 9001, got %v", resp)
	}
	if engines := compute.GetEngines(); len(engines) != 1 || string(engines["100.64.0.1.yolo"]) != yoloToml {
		t.Errorf("expected only the plugin toml of yolo, got %v", engines)
	}
	waitFor(t, "the daemon to be connected", func() bool { return remoteStreams(d, "127.0.0.1") == 1 })
	first := d.remotes[netip.MustParseAddr("127.0.0.1")].conn
	if first.Target() != "passthrough:///127.0.0.1:9100" {
		t.Errorf("expected a connection to 127.0.0.1:9100, got %s", first.Target())
	}

	for i := range 2 {
		if err := stream.Send(&daemonpb.RegisterOrchestratorRequest{}); err != nil {
			t.Fatal(err)
		}
		if resp, err := stream.Recv(); err != nil || resp.HasCompute() {
			t.Fatalf("heartbeat %d: expected an empty answer, got %v, %v", i, resp, err)
		}
	}
	stream.CloseSend()
	if _, err := stream.Recv(); !errors.Is(err, io.EOF) {
		t.Errorf("expected the stream to end, got %v", err)
	}
	waitFor(t, "the daemon to be disconnected", func() bool { return remoteStreams(d, "127.0.0.1") == 0 })

	// Registering again on another port replaces the connection to the daemon
	moved := daemonpb.DaemonRegistration_builder{Vehicles: registration.GetVehicles(), Port: 9200}.Build()
	if _, _, err := register(t, client, moved); err != nil {
		t.Fatalf("register on new port failed: %v", err)
	}
	waitFor(t, "the daemon to be connected again", func() bool { return remoteStreams(d, "127.0.0.1") == 1 })
	if conn := d.remotes[netip.MustParseAddr("127.0.0.1")].conn; len(d.remotes) != 1 || conn.Target() != "passthrough:///127.0.0.1:9200" {
		t.Errorf("expected the connection replaced by one to 127.0.0.1:9200, got %v", d.remotes)
	}
	if first.GetState() != connectivity.Shutdown {
		t.Errorf("expected the old connection closed, got %v", first.GetState())
	}
}

// TestRegisterOrchestratorInvalid ensures that a stream that doesn't open with
// a valid registration of the caller's own vehicles is rejected, and that a
// daemon that stops sending heartbeats is disconnected.
func TestRegisterOrchestratorInvalid(t *testing.T) {
	d, client := newRegistrationOrchestrator(t)
	bad := map[string]struct {
		registration *daemonpb.DaemonRegistration
		code         codes.Code
	}{
		"no registration": {nil, codes.InvalidArgument},
		"no port":         {daemonpb.DaemonRegistration_builder{Vehicles: []string{"127.0.0.1.harpy"}}.Build(), codes.InvalidArgument},
		"other daemon":    {daemonpb.DaemonRegistration_builder{Vehicles: []string{"100.64.0.8.harpy"}, Port: 9100}.Build(), codes.PermissionDenied},
		"no ip":           {daemonpb.DaemonRegistration_builder{Vehicles: []string{"harpy"}, Port: 9100}.Build(), codes.PermissionDenied},
		"no name":         {daemonpb.DaemonRegistration_builder{Vehicles: []string{"127.0.0.1."}, Port: 9100}.Build(), codes.InvalidArgument},
		"ip prefix":       {daemonpb.DaemonRegistration_builder{Vehicles: []string{"127.0.0.10.harpy"}, Port: 9100}.Build(), codes.PermissionDenied},
	}
	for name, tt := range bad {
		if _, _, err := register(t, client, tt.registration); status.Code(err) != tt.code {
			t.Errorf("%s: expected %v, got %v", name, tt.code, err)
		}
	}

	setTimings(t, time.Hour, 100*time.Millisecond, time.Hour, time.Hour)
	stream, _, err := register(t, client, daemonpb.DaemonRegistration_builder{Port: 9100}.Build())
	if err != nil {
		t.Fatalf("register failed: %v", err)
	}
	if _, err := stream.Recv(); status.Code(err) != codes.DeadlineExceeded {
		t.Errorf("expected the stream to time out without heartbeats, got %v", err)
	}
	waitFor(t, "the daemon to be disconnected", func() bool { return remoteStreams(d, "127.0.0.1") == 0 })
}

// fakeOrchestrator answers registrations like an orchestrator, and ends each
// stream after a number of heartbeats.
type fakeOrchestrator struct {
	daemonpb.UnimplementedDaemonServiceServer
	cert       string
	heartbeats int // heartbeats to answer on each stream before ending it
	mu         sync.Mutex
	streams    int // registrations received
	beats      int // heartbeats received
}

func (f *fakeOrchestrator) RegisterOrchestrator(
	stream grpc.BidiStreamingServer[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse],
) error {
	req, err := stream.Recv()
	if err != nil || !req.HasRegistration() {
		return status.Error(codes.InvalidArgument, "no registration")
	}
	f.mu.Lock()
	f.streams++
	f.mu.Unlock()
	compute := daemonpb.RemoteCompute_builder{Cert: f.cert, Port: 9001, Engines: map[string][]byte{"100.64.0.1.yolo": []byte(yoloToml)}}.Build()
	if err := stream.Send(daemonpb.RegisterOrchestratorResponse_builder{Compute: compute}.Build()); err != nil {
		return err
	}
	for range f.heartbeats {
		if _, err := stream.Recv(); err != nil {
			return err
		}
		f.mu.Lock()
		f.beats++
		f.mu.Unlock()
		if err := stream.Send(&daemonpb.RegisterOrchestratorResponse{}); err != nil {
			return err
		}
	}
	return nil
}

// counts returns the registrations and heartbeats received so far.
func (f *fakeOrchestrator) counts() (int, int) {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.streams, f.beats
}

// TestMaintainRegistration ensures that a daemon keeps trying to register with
// an orchestrator that isn't up yet, registers and keeps its remote compute
// service once it is, sends heartbeats, registers again when the stream dies,
// and stops once its context is done.
func TestMaintainRegistration(t *testing.T) {
	if network.Tailscale {
		t.Skip("needs the host network of the notailscale build tag")
	}
	setTimings(t, 10*time.Millisecond, time.Second, 10*time.Millisecond, 50*time.Millisecond)
	der, _, err := generateCert(lcsServerName)
	if err != nil {
		t.Fatal(err)
	}
	fake := &fakeOrchestrator{cert: string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})), heartbeats: 3}

	// The orchestrator's port is reserved, but nothing listens on it at first
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := ln.Addr().String()
	ln.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	host, err := network.NewServer(ctx, "test", "")
	if err != nil {
		t.Fatal(err)
	}
	d := &Daemon{
		Config:  &config.DaemonConfig{Daemon: config.DaemonRoot{Port: 9100, Orchestrator: addr}},
		network: host,
		log:     testLogger(),
	}
	r := newRegistration(listener.NewAcl(nil, nil, true))
	done := make(chan struct{})
	go func() {
		d.maintainRegistration(ctx, r)
		close(done)
	}()

	time.Sleep(100 * time.Millisecond)
	select {
	case <-r.registered:
		t.Fatal("registered before the orchestrator was up")
	default:
	}
	ln, err = net.Listen("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	server := grpc.NewServer()
	daemonpb.RegisterDaemonServiceServer(server, fake)
	go server.Serve(ln)
	defer server.Stop()

	select {
	case <-r.registered:
	case <-time.After(5 * time.Second):
		t.Fatal("never registered once the orchestrator was up")
	}
	d.rcsMu.Lock()
	rcsAddr, engines := d.rcsAddr, d.rcsEngines
	d.rcsMu.Unlock()
	if rcsAddr != "127.0.0.1:9001" || len(engines) != 1 {
		t.Errorf("expected the remote compute service at 127.0.0.1:9001 with yolo, got %s with %v", rcsAddr, engines)
	}
	if ok, code := r.acl.AllowsIp(net.ParseIP("127.0.0.1")); !ok || code != listener.AdminCode {
		t.Errorf("expected the orchestrator granted AdminCode, got %v, %v", ok, code)
	}
	waitFor(t, "registering again after the stream ends", func() bool {
		streams, beats := fake.counts()
		return streams >= 2 && beats >= 3
	})

	cancel()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("registration didn't stop with its context")
	}
}

// TestRegisterOrchestratorLaw ensures that the daemon law lets remote daemons,
// which call with ExternalCode, register while the daemon is online.
func TestRegisterOrchestratorLaw(t *testing.T) {
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		t.Fatal(err)
	}
	p, err := policy.NewPolicy(law, policy.WithLogger(testLogger()))
	if err != nil {
		t.Fatal(err)
	}
	command := "external/" + daemonpb.DaemonService_RegisterOrchestrator_FullMethodName[1:]
	if allowed, _, err := p.SafeCheckAndTransit(context.Background(), command); err != nil || !allowed {
		t.Errorf("expected %s allowed, got %v, %v", command, allowed, err)
	}
}
