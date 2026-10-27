package daemon

import (
	"context"
	"flag"
	"fmt"
	"io"
	"net"
	"net/netip"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	"github.com/adrg/xdg"
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/network"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// testPkg is the uri of the test package, which TestMain installs as pending,
// so that every daemon commits it. Its plugins are echo (an extra), detector
// (an engine) and driver (a vehicle driver), all run by the binary built from
// testdata/plugin.
const testPkg = "example.com/steeleagle/test//pkg"

// Loopback addresses that test daemons are at, so that two daemons in one
// process have different IPs, as on a real network.
var (
	orchAddr  = netip.MustParseAddr("127.0.0.1")
	childAddr = netip.MustParseAddr("127.0.0.2")
)

// testBase is the temporary directory holding the XDG directories for the
// tests. It is kept short, since plugin sockets are made under it.
var testBase string

// havePixi is whether pixi is installed, which running test daemons with
// services requires.
var havePixi bool

func TestMain(m *testing.M) {
	code, err := runTests(m)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		code = 1
	}
	os.Exit(code)
}

// runTests sets up isolated XDG directories with the test package installed,
// shortens the registration timings, and runs the tests.
func runTests(m *testing.M) (int, error) {
	flag.Parse()
	var err error
	testBase, err = os.MkdirTemp("", "sed")
	if err != nil {
		return 0, err
	}
	defer os.RemoveAll(testBase)
	for env, dir := range map[string]string{
		"XDG_DATA_HOME":   "d",
		"XDG_CONFIG_HOME": "c",
		"XDG_RUNTIME_DIR": "r",
	} {
		os.Setenv(env, filepath.Join(testBase, dir))
	}
	xdg.Reload()
	_, err = exec.LookPath("pixi")
	havePixi = err == nil
	if err := installTestPackage(); err != nil {
		return 0, err
	}

	// Timings are shortened so that disconnections are noticed quickly
	RegisterWait = time.Second
	HeartbeatInterval = 100 * time.Millisecond
	HeartbeatTimeout = time.Second
	RegisterBackoffMin = 20 * time.Millisecond
	RegisterBackoffMax = 200 * time.Millisecond
	return m.Run(), nil
}

// installTestPackage installs testdata/pkg, with the plugin binary built into
// it, as a pending package.
func installTestPackage() error {
	pending, err := util.GetPendingDir()
	if err != nil {
		return err
	}
	dir := filepath.Join(pending, getPackageDir(testPkg))
	if err := os.CopyFS(dir, os.DirFS("testdata/pkg")); err != nil {
		return err
	}
	cmd := exec.Command("go", "build", "-o", filepath.Join(dir, "binary"), "./testdata/plugin")
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("couldn't build test plugin: %v\n%s", err, out)
	}
	return os.WriteFile(filepath.Join(dir, PackageUrlFileName), []byte(testPkg), 0644)
}

// requirePixi skips the test if pixi, which runs the test plugins, isn't
// installed.
func requirePixi(t *testing.T) {
	t.Helper()
	if !havePixi {
		t.Skip("pixi not found, skipping test")
	}
}

// testOutput returns stdout when tests are verbose, and discards output
// otherwise.
func testOutput() io.Writer {
	if testing.Verbose() {
		return os.Stdout
	}
	return io.Discard
}

// testLogger returns a logger that only logs when tests are verbose.
func testLogger() zerolog.Logger {
	if testing.Verbose() {
		return zerolog.New(os.Stdout).With().Timestamp().Logger()
	}
	return zerolog.Nop()
}

// linkState is the state of the links between test daemons.
type linkState int

const (
	linkUp        linkState = iota // connections work
	linkCut                        // connections are reset, and dials refused
	linkBlackhole                  // connections and dials stall, as if packets were dropped
)

// fabric is a fake network joining test daemons, which can be cut or
// blackholed and healed. Connections stalled by a blackhole never recover,
// like ones whose peer gave up on them, so a healed fabric only carries new
// connections.
type fabric struct {
	mu      sync.Mutex
	state   linkState
	conns   map[*fabricConn]struct{}
	changed chan struct{} // closed and replaced when the state changes
}

func newFabric() *fabric {
	return &fabric{conns: map[*fabricConn]struct{}{}, changed: make(chan struct{})}
}

// set sets the state of the links, cutting or stalling every open connection
// unless the links are up.
func (f *fabric) set(state linkState) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.state = state
	close(f.changed)
	f.changed = make(chan struct{})
	if state == linkUp {
		return
	}
	for c := range f.conns {
		delete(f.conns, c)
		if state == linkCut {
			c.Conn.Close()
		} else {
			c.stall()
		}
	}
}

// track wraps a connection so that it follows the state of the links.
func (f *fabric) track(c net.Conn) net.Conn {
	fc := &fabricConn{Conn: c, fabric: f, stalled: make(chan struct{}), closed: make(chan struct{})}
	f.mu.Lock()
	defer f.mu.Unlock()
	switch f.state {
	case linkCut:
		c.Close()
	case linkBlackhole:
		fc.stall()
	default:
		f.conns[fc] = struct{}{}
	}
	return fc
}

// wait blocks until the links are up or cut, returning whether they are up.
func (f *fabric) wait(ctx context.Context) (bool, error) {
	for {
		f.mu.Lock()
		state, changed := f.state, f.changed
		f.mu.Unlock()
		if state != linkBlackhole {
			return state == linkUp, nil
		}
		select {
		case <-changed:
		case <-ctx.Done():
			return false, ctx.Err()
		}
	}
}

// fabricConn is a connection on a fabric. Once stalled, it drops everything
// written to it, and reads block until it is closed.
type fabricConn struct {
	net.Conn
	fabric    *fabric
	stallOnce sync.Once
	stalled   chan struct{}
	closeOnce sync.Once
	closed    chan struct{}
}

func (c *fabricConn) stall() {
	c.stallOnce.Do(func() { close(c.stalled) })
}

func (c *fabricConn) isStalled() bool {
	select {
	case <-c.stalled:
		return true
	default:
		return false
	}
}

func (c *fabricConn) Read(b []byte) (int, error) {
	for {
		if c.isStalled() {
			<-c.closed
			return 0, net.ErrClosed
		}
		n, err := c.Conn.Read(b)
		if !c.isStalled() {
			return n, err
		}
	}
}

func (c *fabricConn) Write(b []byte) (int, error) {
	if c.isStalled() {
		return len(b), nil
	}
	return c.Conn.Write(b)
}

func (c *fabricConn) Close() error {
	c.closeOnce.Do(func() { close(c.closed) })
	c.fabric.mu.Lock()
	delete(c.fabric.conns, c)
	c.fabric.mu.Unlock()
	return c.Conn.Close()
}

// fabricListener is a listener on a fabric.
type fabricListener struct {
	net.Listener
	fabric *fabric
}

func (l *fabricListener) Accept() (net.Conn, error) {
	c, err := l.Listener.Accept()
	if err != nil {
		return nil, err
	}
	return l.fabric.track(c), nil
}

// testNet is a daemon's view of a fabric, from its own loopback address.
type testNet struct {
	addr   netip.Addr
	fabric *fabric
}

var _ network.Network = (*testNet)(nil)

func (n *testNet) Listen(protocol string, port int) (net.Listener, error) {
	ln, err := net.Listen(protocol, netip.AddrPortFrom(n.addr, uint16(port)).String())
	if err != nil {
		return nil, err
	}
	return &fabricListener{Listener: ln, fabric: n.fabric}, nil
}

func (n *testNet) Dial(ctx context.Context, protocol, addr string) (net.Conn, error) {
	up, err := n.fabric.wait(ctx)
	if err != nil {
		return nil, err
	}
	if !up {
		return nil, &net.OpError{Op: "dial", Net: protocol, Err: syscall.ECONNREFUSED}
	}
	d := net.Dialer{LocalAddr: &net.TCPAddr{IP: n.addr.AsSlice()}}
	c, err := d.DialContext(ctx, protocol, addr)
	if err != nil {
		return nil, err
	}
	return n.fabric.track(c), nil
}

func (n *testNet) Resolve(ctx context.Context, host string) ([]netip.Addr, error) {
	addr, err := netip.ParseAddr(host)
	if err != nil {
		return nil, fmt.Errorf("no host %q", host)
	}
	return []netip.Addr{addr}, nil
}

func (n *testNet) LocalAddr(ctx context.Context, remote netip.Addr) (netip.Addr, error) {
	return n.addr, nil
}

func (n *testNet) Close() {}

// freePort returns a TCP port that is free on the loopback addresses.
func freePort(t *testing.T) int {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	return ln.Addr().(*net.TCPAddr).Port
}

// testService is a service in a test daemon config.
type testService struct {
	name, typ, plugin, args, auth string
}

// echo returns an extra service running the echo plugin with args, a TOML
// inline table.
func echo(name, args string) testService {
	return testService{name: name, typ: "extra", plugin: "echo", args: args}
}

// testConfig returns a daemon config with the given orchestrator, which may be
// empty, and services, on free ports.
func testConfig(t *testing.T, hostname, orchestrator string, services ...testService) string {
	t.Helper()
	return testConfigOnPort(t, freePort(t), hostname, orchestrator, services...)
}

// testConfigOnPort is testConfig on the given daemon port.
func testConfigOnPort(t *testing.T, port int, hostname, orchestrator string, services ...testService) string {
	t.Helper()
	var b strings.Builder
	fmt.Fprintf(&b, "[daemon]\nport = %d\nlcs = %d\nhostname = %q\n", port, freePort(t), hostname)
	if orchestrator != "" {
		fmt.Fprintf(&b, "orchestrator = %q\n", orchestrator)
	}
	for _, s := range services {
		fmt.Fprintf(&b, "\n[[services]]\nname = %q\ntype = %q\n", s.name, s.typ)
		if s.auth != "" {
			fmt.Fprintf(&b, "auth = %q\n", s.auth)
		}
		fmt.Fprintf(&b, "[services.plugin]\nplugin = %q\npackage = %q\n", s.plugin, testPkg)
		if s.args != "" {
			fmt.Fprintf(&b, "args = %s\n", s.args)
		}
	}
	return b.String()
}

// testDaemon is a daemon run by a test, with a client on its control socket.
type testDaemon struct {
	*Daemon
	t      *testing.T
	ctl    *grpc.ClientConn
	client daemonpb.DaemonServiceClient
	cancel context.CancelFunc
	done   chan error // receives the result of Run
	result error      // result of Run, once received
	exited bool
}

// newTestDaemon creates a daemon from config on n. It is stopped when the
// test ends, if it is running.
func newTestDaemon(t *testing.T, n *testNet, config string) *testDaemon {
	t.Helper()
	// The control socket is kept out of t.TempDir, whose long paths can
	// exceed the limit for socket paths
	dir, err := os.MkdirTemp(testBase, "t")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	path := filepath.Join(dir, ConfigFileName)
	if err := os.WriteFile(path, []byte(config), 0644); err != nil {
		t.Fatal(err)
	}
	d, err := NewDaemon(
		WithConfigPath(path),
		WithNetwork(n),
		WithSocketPath(filepath.Join(dir, "ctl.sock")),
		WithLogger(testLogger()),
	)
	if err != nil {
		t.Fatal(err)
	}
	ctl, err := grpc.NewClient("unix://"+d.socketPath, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	td := &testDaemon{Daemon: d, t: t, ctl: ctl, client: daemonpb.NewDaemonServiceClient(ctl)}
	t.Cleanup(func() {
		td.stop()
		ctl.Close()
		if t.Failed() {
			logServiceLogs(t)
		}
	})
	return td
}

// logServiceLogs logs the logs of every service, which have the output of
// their plugins.
func logServiceLogs(t *testing.T) {
	dir := filepath.Join(xdg.DataHome, "steeleagle", "logs")
	filepath.WalkDir(dir, func(path string, e os.DirEntry, err error) error {
		if err == nil && !e.IsDir() {
			b, _ := os.ReadFile(path)
			t.Logf("%s:\n%s", path, b)
		}
		return nil
	})
}

// start runs the daemon in the background, without waiting for it to serve.
func (td *testDaemon) start() {
	ctx, cancel := context.WithCancel(context.Background())
	td.cancel = cancel
	td.done = make(chan error, 1)
	go func() { td.done <- td.Run(ctx) }()
}

// run runs the daemon in the background, and waits until it serves calls on
// its control socket.
func (td *testDaemon) run() {
	td.t.Helper()
	td.start()
	td.waitServing()
}

// waitServing waits until the daemon serves calls on its control socket.
func (td *testDaemon) waitServing() {
	td.t.Helper()
	eventually(td.t, 30*time.Second, func() error {
		select {
		case td.result = <-td.done:
			td.exited = true
			td.t.Fatalf("Run() = %v before serving", td.result)
		default:
		}
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		_, err := td.client.GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
		return err
	})
}

// wait waits for Run to return, failing the test if it doesn't in time.
func (td *testDaemon) wait() error {
	td.t.Helper()
	if td.exited {
		return td.result
	}
	select {
	case td.result = <-td.done:
		td.exited = true
		return td.result
	case <-time.After(30 * time.Second):
		td.t.Fatal("daemon didn't stop")
		return nil
	}
}

// stop stops the daemon, if it was started, returning the result of Run.
func (td *testDaemon) stop() error {
	if td.cancel == nil {
		return nil
	}
	td.cancel()
	return td.wait()
}

// ctx returns a context for a call to the daemon, failing after timeout.
func callCtx(t *testing.T, timeout time.Duration) context.Context {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	t.Cleanup(cancel)
	return ctx
}

// routed returns a context for a call that the daemon routes to key.
func routed(t *testing.T, key string) context.Context {
	return router.Embed(callCtx(t, 5*time.Second), key)
}

// listServices lists the services of a daemon.
func (td *testDaemon) listServices() (*daemonpb.ListServicesResponse, error) {
	return td.client.ListServices(callCtx(td.t, 5*time.Second), &daemonpb.ListServicesRequest{})
}

// connected returns whether the daemon reports that it is connected to its
// orchestrator.
func (td *testDaemon) connected() bool {
	td.t.Helper()
	resp, err := td.client.GetConnectionStatus(callCtx(td.t, 5*time.Second), &daemonpb.GetConnectionStatusRequest{})
	if err != nil {
		td.t.Fatalf("GetConnectionStatus() = %v", err)
	}
	return resp.GetConnected()
}

// running returns the names of the services in a listing, each with whether
// it is running.
func running(resp *daemonpb.ListServicesResponse) map[string]bool {
	out := map[string]bool{}
	for _, s := range resp.GetServices() {
		out[s.GetName()] = s.GetRunning()
	}
	return out
}

// unavailable returns the IPs listed as unavailable in a listing.
func unavailable(resp *daemonpb.ListServicesResponse) []string {
	var out []string
	for _, u := range resp.GetUnavailable() {
		out = append(out, u.GetIp())
	}
	return out
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

// readLog reads the log of a service.
func readLog(t *testing.T, name string) string {
	t.Helper()
	path, err := util.GetLogByName(name)
	if err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

// standalone returns a daemon without an orchestrator, running services.
func standalone(t *testing.T, services ...testService) *testDaemon {
	t.Helper()
	n := &testNet{addr: orchAddr, fabric: newFabric()}
	return newTestDaemon(t, n, testConfig(t, "solo", "", services...))
}

// pluginRunning returns whether the plugin of a service is running, and
// whether the service has a plugin at all.
func (td *testDaemon) pluginRunning(name string) (bool, bool) {
	td.svcMu.RLock()
	defer td.svcMu.RUnlock()
	p, ok := td.plugins[name]
	if !ok {
		return false, false
	}
	return p.plugin.Running(), true
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

// newIdleDaemon returns a daemon at addr that isn't run, for testing its
// parts.
func newIdleDaemon(t *testing.T, addr netip.Addr, config string) *Daemon {
	t.Helper()
	td := newTestDaemon(t, &testNet{addr: addr, fabric: newFabric()}, config)
	td.netAddr = addr
	return td.Daemon
}

// installSimulator installs a simulator package with a plugin for simulated
// vehicles, returning its uri. It lasts until the next daemon is created.
func installSimulator(t *testing.T) string {
	t.Helper()
	const uri = "example.com/steeleagle/sim"
	pkg, err := util.GetPackageDir()
	if err != nil {
		t.Fatal(err)
	}
	dir := filepath.Join(pkg, getPackageDir(uri))
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	plugin := "[plugin]\nname = \"Simulated vehicle\"\ntype = \"driver\"\n"
	if err := os.WriteFile(filepath.Join(dir, "sim_vehicle"+PluginFileSuffix), []byte(plugin), 0644); err != nil {
		t.Fatal(err)
	}
	return uri
}
