package daemon

import (
	"context"
	"crypto/x509"
	"errors"
	"fmt"
	"net"
	"net/netip"
	"os"
	"runtime"
	"slices"
	"strings"
	"sync"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// pair is an orchestrator and a child daemon on one fabric.
type pair struct {
	fabric      *fabric
	orch, child *testDaemon
	orchPort    int
}

// newPair creates an orchestrator and a child daemon registering with it,
// without running them.
func newPair(t *testing.T, orchServices, childServices []testService) *pair {
	t.Helper()
	p := &pair{fabric: newFabric(), orchPort: freePort(t)}
	p.orch = newTestDaemon(t, &testNet{addr: orchAddr, fabric: p.fabric},
		testConfigOnPort(t, p.orchPort, "orch", "", orchServices...))
	p.child = newTestDaemon(t, &testNet{addr: childAddr, fabric: p.fabric},
		testConfig(t, "child", p.orchAddr(), childServices...))
	return p
}

// orchAddr is the address of the orchestrator, as the child is configured
// with it.
func (p *pair) orchAddr() string {
	return netip.AddrPortFrom(orchAddr, uint16(p.orchPort)).String()
}

// runPair runs an orchestrator with service o, and a registered child with
// service c.
func runPair(t *testing.T) *pair {
	t.Helper()
	requirePixi(t)
	p := newPair(t, []testService{echo("o", "{}")}, []testService{echo("c", "{}")})
	p.orch.run()
	p.child.run()
	return p
}

// setTiming sets a registration timing for the length of a test.
func setTiming(t *testing.T, v *time.Duration, d time.Duration) {
	old := *v
	*v = d
	t.Cleanup(func() { *v = old })
}

// expectListing waits until the orchestrator lists exactly the given running
// services, and the given IPs as unavailable.
func expectListing(t *testing.T, d *testDaemon, timeout time.Duration, services []string, unavailableIps []string) {
	t.Helper()
	eventually(t, timeout, func() error {
		resp, err := d.listServices()
		if err != nil {
			return err
		}
		var got []string
		for name, running := range running(resp) {
			if !running {
				return fmt.Errorf("service %s isn't running", name)
			}
			got = append(got, name)
		}
		slices.Sort(got)
		if !slices.Equal(got, services) {
			return fmt.Errorf("services = %v, want %v", got, services)
		}
		if got := unavailable(resp); !slices.Equal(got, unavailableIps) {
			return fmt.Errorf("unavailable = %v, want %v", got, unavailableIps)
		}
		return nil
	})
}

// expectConnected waits until the daemon reports whether it is connected.
func expectConnected(t *testing.T, d *testDaemon, timeout time.Duration, want bool) {
	t.Helper()
	eventually(t, timeout, func() error {
		if got := d.connected(); got != want {
			return fmt.Errorf("connected = %v, want %v", got, want)
		}
		return nil
	})
}

// checkHealth calls the health service of the plugin of a service, through
// the orchestrator.
func checkHealth(t *testing.T, orch *testDaemon, service string, timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(routed(t, service), timeout)
	defer cancel()
	resp, err := healthpb.NewHealthClient(orch.ctl).Check(ctx, &healthpb.HealthCheckRequest{})
	if err == nil && resp.GetStatus() != healthpb.HealthCheckResponse_SERVING {
		err = fmt.Errorf("status = %v", resp.GetStatus())
	}
	return err
}

var (
	both      = []string{"127.0.0.1.o", "127.0.0.2.c"}
	orchOnly  = []string{"127.0.0.1.o"}
	childOnly = []string{"127.0.0.2.c"}
)

// TestRegister checks that a child registers with its orchestrator, which
// then lists the child's services and routes calls to them and to the child.
func TestRegister(t *testing.T) {
	p := runPair(t)
	if !p.child.connected() {
		t.Error("child isn't connected")
	}
	expectListing(t, p.orch, time.Second, both, nil)
	// The child only lists its own
	expectListing(t, p.child, time.Second, childOnly, nil)

	// The orchestrator lists the child as a remote, with its platform
	listing, err := p.orch.listServices()
	if err != nil {
		t.Fatal(err)
	}
	if r := listing.GetRemotes(); len(r) != 1 || r[0].GetIp() != "127.0.0.2" ||
		r[0].GetHostname() != "child" || r[0].GetOs() != runtime.GOOS ||
		r[0].GetArch() != runtime.GOARCH || r[0].GetError() != "" {
		t.Errorf("remotes = %v, want the child on this platform", r)
	}

	// The child knows its orchestrator's services
	p.child.orchMu.RLock()
	orch := p.child.orch
	p.child.orchMu.RUnlock()
	if orch == nil || orch.hostname != "orch" || orch.ip != "127.0.0.1" ||
		len(orch.services) != 1 || orch.services[0].name != "127.0.0.1.o" || orch.services[0].local {
		t.Errorf("orchestrator info = %+v, want orch with service o", orch)
	}
	// Vehicles on the child can reach the orchestrator's compute service
	if orch == nil {
		t.Fatal("child has no orchestrator info")
	}
	if orch.lcsPort != p.orch.Config.Daemon.Lcs || !slices.Equal(orch.cert, p.orch.cert) {
		t.Errorf("orchestrator compute service = port %d, cert %x, want port %d, cert %x",
			orch.lcsPort, orch.cert, p.orch.Config.Daemon.Lcs, p.orch.cert)
	}
	if _, err := x509.ParseCertificate(orch.cert); err != nil {
		t.Errorf("orchestrator cert isn't DER: %v", err)
	}

	// Calls are routed to the child by its IP, and to its services by name
	resp, err := p.orch.client.GetConfiguration(routed(t, "127.0.0.2"), &daemonpb.GetConfigurationRequest{})
	if err != nil {
		t.Fatal(err)
	}
	want, _ := os.ReadFile(p.child.configPath)
	if string(resp.GetConfigToml()) != string(want) {
		t.Errorf("routed GetConfiguration() = %q, want the child's config", resp.GetConfigToml())
	}
	if err := checkHealth(t, p.orch, "127.0.0.2.c", 5*time.Second); err != nil {
		t.Errorf("health check of the child's service = %v", err)
	}
	if err := checkHealth(t, p.orch, "127.0.0.1.o", 5*time.Second); err != nil {
		t.Errorf("health check of the orchestrator's service = %v", err)
	}

	// The child's services are restarted by the child
	_, err = p.orch.client.RestartService(callCtx(t, 30*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.2.c"}.Build())
	if err != nil {
		t.Fatal(err)
	}
	if log := readLog(t, "127.0.0.2.c"); strings.Count(log, "plugin=echo.plugin.toml") != 2 {
		t.Errorf("child service log = %q, want a line from each run", log)
	}
	if log := readLog(t, "127.0.0.1.o"); strings.Count(log, "plugin=echo.plugin.toml") != 1 {
		t.Errorf("orchestrator service log = %q, want it started once", log)
	}
	_, err = p.orch.client.RestartService(callCtx(t, 5*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.2.nope"}.Build())
	expectCode(t, err, codes.NotFound)
}

// TestLockedChild checks that a child only takes control calls from its
// orchestrator, while its own control socket is read only.
func TestLockedChild(t *testing.T) {
	p := runPair(t)
	_, err := p.child.client.Restart(callCtx(t, 5*time.Second), &daemonpb.RestartRequest{})
	expectCode(t, err, codes.PermissionDenied)
	_, err = p.child.client.RestartService(callCtx(t, 5*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.2.c"}.Build())
	expectCode(t, err, codes.PermissionDenied)
	if _, err := p.child.listServices(); err != nil {
		t.Errorf("ListServices() on the child = %v, want nil", err)
	}
	// Through the orchestrator, the child takes control calls, and answers
	// them before it ends its registration
	if _, err := p.orch.client.Restart(routed(t, "127.0.0.2"), &daemonpb.RestartRequest{}); err != nil {
		t.Errorf("Restart() through the orchestrator = %v", err)
	}
	if err := p.child.wait(); !errors.Is(err, ErrRestart) {
		t.Errorf("child Run() = %v, want ErrRestart", err)
	}
	// The child left, so the orchestrator stops listing it
	expectListing(t, p.orch, 2*time.Second, orchOnly, nil)
}

// TestCut checks that when the link to the orchestrator is cut, the child
// reports that it is disconnected but keeps running its services, the
// orchestrator stops listing and routing to it, and both recover once the
// link is back, over several flaps.
func TestCut(t *testing.T) {
	p := runPair(t)
	for i := range 3 {
		p.fabric.set(linkCut)
		expectConnected(t, p.child, 2*time.Second, false)
		// The registration ends with its connection, before any heartbeat
		// times out
		expectListing(t, p.orch, HeartbeatTimeout/2, orchOnly, nil)
		_, err := p.orch.client.RestartService(callCtx(t, 5*time.Second),
			daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.2.c"}.Build())
		expectCode(t, err, codes.NotFound)
		if err := checkHealth(t, p.orch, "127.0.0.2.c", time.Second); status.Code(err) == codes.OK {
			t.Error("call to a disconnected child's service succeeded")
		}
		// The child keeps running on its own
		expectListing(t, p.child, time.Second, childOnly, nil)

		p.fabric.set(linkUp)
		expectConnected(t, p.child, 5*time.Second, true)
		expectListing(t, p.orch, 5*time.Second, both, nil)
		if err := checkHealth(t, p.orch, "127.0.0.2.c", 5*time.Second); err != nil {
			t.Errorf("flap %d: health check after reconnecting = %v", i, err)
		}
	}
}

// TestBlackhole checks that when the link silently drops everything,
// listings on the orchestrator still answer in time, with the child listed
// as unavailable, until its heartbeat times out and it is dropped, and that
// both recover once the link is back.
func TestBlackhole(t *testing.T) {
	setTiming(t, &HeartbeatTimeout, 3*time.Second)
	p := runPair(t)
	expectListing(t, p.orch, time.Second, both, nil)

	p.fabric.set(linkBlackhole)
	start := time.Now()
	resp, err := p.orch.listServices()
	if err != nil {
		t.Fatal(err)
	}
	if took := time.Since(start); took > Deadline+time.Second {
		t.Errorf("ListServices() took %v during a blackhole, want about %v", took, Deadline)
	}
	if got := running(resp); len(got) != 1 || !got["127.0.0.1.o"] {
		t.Errorf("services = %v, want only the orchestrator's", got)
	}
	if got := unavailable(resp); !slices.Equal(got, []string{"127.0.0.2"}) {
		t.Errorf("unavailable = %v, want the child", got)
	} else if r := resp.GetRemotes()[0]; r.GetHostname() != "child" || r.GetError() == "" {
		t.Errorf("unavailable child = %v, want its hostname and a reason", r)
	}
	// Calls to the child fail at their deadline, and don't hang
	start = time.Now()
	if err := checkHealth(t, p.orch, "127.0.0.2.c", 500*time.Millisecond); status.Code(err) != codes.DeadlineExceeded {
		t.Errorf("call during a blackhole = %v, want DeadlineExceeded", err)
	}
	if took := time.Since(start); took > 2*time.Second {
		t.Errorf("call during a blackhole took %v", took)
	}
	// Forwarded restarts give up at their deadline, though the caller's is
	// later
	setTiming(t, &RestartDeadline, 500*time.Millisecond)
	start = time.Now()
	_, err = p.orch.client.RestartService(callCtx(t, 10*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.2.c"}.Build())
	expectCode(t, err, codes.DeadlineExceeded)
	if took := time.Since(start); took > 2*time.Second {
		t.Errorf("forwarded restart during a blackhole took %v, want about %v", took, RestartDeadline)
	}
	// The child still thinks it is connected, until its heartbeat times out
	if !p.child.connected() {
		t.Error("child noticed the blackhole before its heartbeat timed out")
	}

	// Both sides time out the heartbeat
	expectConnected(t, p.child, 2*HeartbeatTimeout, false)
	expectListing(t, p.orch, 2*HeartbeatTimeout, orchOnly, nil)

	p.fabric.set(linkUp)
	expectConnected(t, p.child, 5*time.Second, true)
	expectListing(t, p.orch, 5*time.Second, both, nil)
}

// TestBlackholeHeals checks that a child whose link heals before its
// heartbeat times out stays registered.
func TestBlackholeHeals(t *testing.T) {
	setTiming(t, &HeartbeatTimeout, 3*time.Second)
	p := runPair(t)
	p.fabric.set(linkBlackhole)
	time.Sleep(HeartbeatTimeout / 3)
	// Stalled connections stay dead, as if the peer had given up on them, so
	// the registration is only recovered by reconnecting
	p.fabric.set(linkUp)
	expectConnected(t, p.child, 3*HeartbeatTimeout, true)
	expectListing(t, p.orch, 3*HeartbeatTimeout, both, nil)
}

// TestChildBeforeOrchestrator checks that a child waits for its
// orchestrator before it serves, then registers once it is up.
func TestChildBeforeOrchestrator(t *testing.T) {
	requirePixi(t)
	p := newPair(t, []testService{echo("o", "{}")}, []testService{echo("c", "{}")})
	p.child.start()
	time.Sleep(500 * time.Millisecond)
	if _, err := p.child.client.GetConfiguration(callCtx(t, 200*time.Millisecond), &daemonpb.GetConfigurationRequest{}); err == nil {
		t.Error("child serves before it registered")
	}
	if _, ok := p.child.pluginRunning("127.0.0.2.c"); ok {
		t.Error("child started its services before it registered")
	}
	p.orch.run()
	p.child.waitServing()
	if !p.child.connected() {
		t.Error("child isn't connected")
	}
	expectListing(t, p.orch, 2*time.Second, both, nil)
}

// TestChildGivesUp checks that a child waiting for its orchestrator stops
// when it is canceled.
func TestChildGivesUp(t *testing.T) {
	p := newPair(t, nil, nil)
	p.child.start()
	time.Sleep(300 * time.Millisecond)
	p.child.cancel()
	if err := p.child.wait(); err == nil {
		t.Error("Run() = nil, want the reason it never registered")
	}
}

// TestOrchestratorRestart checks that a child reconnects to its orchestrator
// after the orchestrator restarts.
func TestOrchestratorRestart(t *testing.T) {
	p := runPair(t)
	if err := p.orch.stop(); err != nil {
		t.Fatal(err)
	}
	expectConnected(t, p.child, 2*time.Second, false)
	expectListing(t, p.child, time.Second, childOnly, nil)

	orch := newTestDaemon(t, &testNet{addr: orchAddr, fabric: p.fabric},
		testConfigOnPort(t, p.orchPort, "orch", "", echo("o", "{}")))
	orch.run()
	expectConnected(t, p.child, 5*time.Second, true)
	expectListing(t, orch, 5*time.Second, both, nil)
	if err := checkHealth(t, orch, "127.0.0.2.c", 5*time.Second); err != nil {
		t.Errorf("health check through the new orchestrator = %v", err)
	}
}

// TestChildStops checks that an orchestrator drops a child as soon as it
// stops, without waiting for its heartbeat to time out.
func TestChildStops(t *testing.T) {
	setTiming(t, &HeartbeatTimeout, 10*time.Second)
	p := runPair(t)
	if err := p.child.stop(); err != nil {
		t.Fatal(err)
	}
	expectListing(t, p.orch, 2*time.Second, orchOnly, nil)
}

// TestDegradedChild checks that a child whose service failed to start
// registers with it, so that the orchestrator lists the service as not
// running, with why, and can fix it.
func TestDegradedChild(t *testing.T) {
	requirePixi(t)
	p := newPair(t, []testService{echo("o", "{}")}, []testService{echo("c", `{ fail = true }`)})
	p.orch.run()
	p.child.run()
	resp, err := p.orch.listServices()
	if err != nil {
		t.Fatal(err)
	}
	if got := running(resp); len(got) != 2 || !got["127.0.0.1.o"] || got["127.0.0.2.c"] {
		t.Errorf("services = %v, want the orchestrator's running, and the child's stopped", got)
	}
	for _, s := range resp.GetServices() {
		if s.GetName() == "127.0.0.2.c" && s.GetError() == "" {
			t.Error("child's failed service has no error")
		}
	}
	if u := unavailable(resp); len(u) != 0 {
		t.Errorf("unavailable = %v, want none", u)
	}
	_, err = p.orch.client.RestartService(callCtx(t, 5*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.2.c"}.Build())
	expectCode(t, err, codes.Internal, "127.0.0.2.c")

	// The orchestrator can fix the child
	config := testConfig(t, "child", p.orchAddr(), echo("c", "{}"))
	_, err = p.orch.client.Configure(routed(t, "127.0.0.2"), daemonpb.ConfigureRequest_builder{ConfigToml: config}.Build())
	if err != nil {
		t.Errorf("Configure() through the orchestrator = %v", err)
	}
	if err := p.child.wait(); !errors.Is(err, ErrRestart) {
		t.Errorf("child Run() = %v, want ErrRestart", err)
	}
}

// rawRegistration is a registration stream to an orchestrator, from addr,
// standing in for a child daemon.
type rawRegistration struct {
	conn   *grpc.ClientConn
	stream grpc.BidiStreamingClient[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse]
	cancel context.CancelFunc
}

// register opens a registration stream to the orchestrator from addr, with
// metadata pairs kv.
func (p *pair) register(t *testing.T, addr netip.Addr, kv ...string) *rawRegistration {
	t.Helper()
	n := &testNet{addr: addr, fabric: p.fabric}
	conn, err := grpc.NewClient("passthrough:///"+p.orchAddr(),
		grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return n.Dial(ctx, "tcp", addr)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	ctx = metadata.AppendToOutgoingContext(ctx, kv...)
	stream, err := daemonpb.NewDaemonServiceClient(conn).RegisterOrchestrator(ctx)
	if err != nil {
		t.Fatal(err)
	}
	r := &rawRegistration{conn: conn, stream: stream, cancel: cancel}
	t.Cleanup(r.close)
	return r
}

// send sends a registration with the given port and services, and returns
// the answer.
func (r *rawRegistration) send(port int32, services ...*daemonpb.Service) (*daemonpb.RegisterOrchestratorResponse, error) {
	err := r.stream.Send(daemonpb.RegisterOrchestratorRequest_builder{
		Services: services,
		Hostname: "raw",
		Port:     port,
	}.Build())
	if err != nil {
		return nil, err
	}
	return r.stream.Recv()
}

func (r *rawRegistration) close() {
	r.cancel()
	r.conn.Close()
}

func service(name string) *daemonpb.Service {
	return daemonpb.Service_builder{Name: name, Category: daemonpb.ServiceCategory_SERVICE_CATEGORY_EXTRA}.Build()
}

// TestRegistrationValidation checks that an orchestrator only lets a daemon
// register its own services, at a valid port, in time.
func TestRegistrationValidation(t *testing.T) {
	p := newPair(t, nil, nil)
	p.orch.run()
	raw := netip.MustParseAddr("127.0.0.3")
	tests := []struct {
		name     string
		md       []string
		port     int32
		services []*daemonpb.Service
		code     codes.Code
	}{
		{"another daemon's service", nil, 9000, []*daemonpb.Service{service("127.0.0.3.a"), service("127.0.0.9.b")}, codes.PermissionDenied},
		{"a service with a longer IP", nil, 9000, []*daemonpb.Service{service("127.0.0.33.a")}, codes.PermissionDenied},
		{"an unqualified service", nil, 9000, []*daemonpb.Service{service("a")}, codes.PermissionDenied},
		{"a spoofed caller", []string{callerHeader, "127.0.0.9:1"}, 9000, []*daemonpb.Service{service("127.0.0.9.a")}, codes.PermissionDenied},
		{"no port", nil, 0, nil, codes.InvalidArgument},
		{"a port out of range", nil, 65536, nil, codes.InvalidArgument},
		{"a bad config", nil, 9000, []*daemonpb.Service{daemonpb.Service_builder{Name: "127.0.0.3.a", Config: []byte("[x")}.Build()}, codes.InvalidArgument},
	}
	for _, tt := range tests {
		reg := p.register(t, raw, tt.md...)
		_, err := reg.send(tt.port, tt.services...)
		if status.Code(err) != tt.code {
			t.Errorf("registration with %s = %v, want %v", tt.name, err, tt.code)
		}
		reg.close()
	}
	if len(p.orch.listRemotes()) != 0 {
		t.Error("a rejected daemon was registered")
	}

	// A daemon that never registers is dropped
	reg := p.register(t, raw)
	start := time.Now()
	if _, err := reg.stream.Recv(); status.Code(err) != codes.DeadlineExceeded {
		t.Errorf("silent registration = %v, want DeadlineExceeded", err)
	}
	if took := time.Since(start); took < RegisterWait/2 || took > 3*RegisterWait {
		t.Errorf("silent registration was dropped after %v, want about %v", took, RegisterWait)
	}

	// A valid registration is answered with the orchestrator's services
	reg = p.register(t, raw)
	resp, err := reg.send(9000, service("127.0.0.3.a"))
	if err != nil {
		t.Fatal(err)
	}
	if resp.GetHostname() != "orch" {
		t.Errorf("orchestrator hostname = %q, want orch", resp.GetHostname())
	}
	// The registered daemon isn't there to answer
	expectListing(t, p.orch, 3*time.Second, nil, []string{"127.0.0.3"})
}

// TestReregistration checks that a daemon that registers again, before its
// old registration ended, replaces it, and that the old one ending doesn't
// remove the new one.
func TestReregistration(t *testing.T) {
	p := newPair(t, nil, nil)
	p.orch.run()
	raw := netip.MustParseAddr("127.0.0.3")
	first := p.register(t, raw)
	if _, err := first.send(9000, service("127.0.0.3.a")); err != nil {
		t.Fatal(err)
	}
	if p.orch.remoteFor("127.0.0.3.a") == nil {
		t.Fatal("service of the registered daemon isn't known")
	}
	second := p.register(t, raw)
	if _, err := second.send(9001, service("127.0.0.3.b")); err != nil {
		t.Fatal(err)
	}
	if p.orch.remoteFor("127.0.0.3.a") != nil || p.orch.remoteFor("127.0.0.3.b") == nil {
		t.Error("new registration didn't replace the old one")
	}
	first.close()
	time.Sleep(200 * time.Millisecond)
	if p.orch.remoteFor("127.0.0.3.b") == nil {
		t.Error("old registration ending removed the new one")
	}
	if remotes := p.orch.listRemotes(); len(remotes) != 1 {
		t.Errorf("remotes = %d, want 1", len(remotes))
	}
	second.close()
	eventually(t, 2*time.Second, func() error {
		if len(p.orch.listRemotes()) != 0 {
			return errors.New("daemon still registered")
		}
		return nil
	})
}

// TestHeartbeatTimeout checks that an orchestrator drops a daemon that
// registered, then stopped sending heartbeats.
func TestHeartbeatTimeout(t *testing.T) {
	p := newPair(t, nil, nil)
	p.orch.run()
	reg := p.register(t, netip.MustParseAddr("127.0.0.3"))
	if _, err := reg.send(9000, service("127.0.0.3.a")); err != nil {
		t.Fatal(err)
	}
	start := time.Now()
	if _, err := reg.stream.Recv(); status.Code(err) != codes.DeadlineExceeded {
		t.Errorf("registration without heartbeats = %v, want DeadlineExceeded", err)
	}
	if took := time.Since(start); took < HeartbeatTimeout/2 {
		t.Errorf("registration dropped after %v, before its heartbeat timed out", took)
	}
	if len(p.orch.listRemotes()) != 0 {
		t.Error("daemon still registered after its heartbeat timed out")
	}
}

// TestFlappingStress checks that an orchestrator keeps answering while the
// link to its child flaps between up, cut and blackholed, under concurrent
// listings, restarts and routed calls, and that it is consistent once the
// link is back.
func TestFlappingStress(t *testing.T) {
	requirePixi(t)
	p := newPair(t, []testService{echo("o", "{}")}, []testService{echo("c", "{}"), echo("d", "{}")})
	p.orch.run()
	p.child.run()

	ctx, cancel := context.WithCancel(context.Background())
	var wg sync.WaitGroup
	var mu sync.Mutex
	var listings, failedListings int
	worker := func(f func()) {
		wg.Go(func() {
			for ctx.Err() == nil {
				f()
			}
		})
	}
	// Listings on the orchestrator always answer, and in time
	for range 3 {
		worker(func() {
			start := time.Now()
			_, err := p.orch.client.ListServices(callCtx(t, 10*time.Second), &daemonpb.ListServicesRequest{})
			mu.Lock()
			defer mu.Unlock()
			listings++
			if err != nil {
				failedListings++
				t.Errorf("ListServices() = %v", err)
			}
			if took := time.Since(start); took > Deadline+2*time.Second {
				t.Errorf("ListServices() took %v", took)
			}
		})
	}
	// Restarts and routed calls may fail while the link is down, but return
	worker(func() {
		p.orch.client.RestartService(callCtx(t, 10*time.Second),
			daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.2.c"}.Build())
	})
	worker(func() {
		p.orch.client.RestartService(callCtx(t, 10*time.Second),
			daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.1.o"}.Build())
	})
	worker(func() {
		checkHealth(t, p.orch, "127.0.0.2.d", time.Second)
		p.orch.client.GetConfiguration(routed(t, "127.0.0.2"), &daemonpb.GetConfigurationRequest{})
	})
	worker(func() {
		p.child.connected()
		p.child.listServices()
	})

	for _, state := range []linkState{linkCut, linkUp, linkBlackhole, linkUp, linkCut, linkBlackhole, linkCut, linkUp} {
		p.fabric.set(state)
		time.Sleep(700 * time.Millisecond)
	}
	cancel()
	wg.Wait()
	t.Logf("%d listings, %d failed", listings, failedListings)

	expectConnected(t, p.child, 5*time.Second, true)
	expectListing(t, p.orch, 30*time.Second, []string{"127.0.0.1.o", "127.0.0.2.c", "127.0.0.2.d"}, nil)
	if err := checkHealth(t, p.orch, "127.0.0.2.d", 5*time.Second); err != nil {
		t.Errorf("health check after flapping = %v", err)
	}
}
