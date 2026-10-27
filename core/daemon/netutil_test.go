package daemon

import (
	"context"
	"net"
	"net/netip"
	"slices"
	"testing"

	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

// TestOrchestratorHost checks that the orchestrator host is taken from the
// config with or without a port, including IPv6 addresses.
func TestOrchestratorHost(t *testing.T) {
	tests := map[string]string{
		"orch":            "orch",
		"orch:9000":       "orch",
		"10.0.0.1":        "10.0.0.1",
		"10.0.0.1:9000":   "10.0.0.1",
		"fd7a::1":         "fd7a::1",
		"[fd7a::1]":       "fd7a::1",
		"[fd7a::1]:9000":  "fd7a::1",
		"orch.tail.net.":  "orch.tail.net.",
		"orch.tail.net:1": "orch.tail.net",
	}
	for orch, want := range tests {
		d := &Daemon{Config: &config.DaemonConfig{Daemon: config.DaemonRoot{Orchestrator: orch}}}
		if got := d.orchestratorHost(); got != want {
			t.Errorf("orchestratorHost() of %q = %q, want %q", orch, got, want)
		}
	}
}

// TestQualify checks that names are qualified with the daemon's address,
// once it has one.
func TestQualify(t *testing.T) {
	d := &Daemon{}
	if got := d.qualify("a"); got != "a" {
		t.Errorf("qualify() without an address = %q, want %q", got, "a")
	}
	d.netAddr = netip.MustParseAddr("100.64.0.1")
	if got := d.qualify("a"); got != "100.64.0.1.a" {
		t.Errorf("qualify() = %q, want %q", got, "100.64.0.1.a")
	}
	if got := d.qualify(""); got != "" {
		t.Errorf("qualify() of an empty name = %q, want it empty", got)
	}
	d.netAddr = netip.MustParseAddr("fd7a::1")
	if got := d.qualify("a"); got != "fd7a::1.a" {
		t.Errorf("qualify() = %q, want %q", got, "fd7a::1.a")
	}
}

// TestCallerIp checks that the caller IP is read from the call metadata,
// unmapping IPv4-mapped IPv6 addresses.
func TestCallerIp(t *testing.T) {
	valid := map[string]string{
		"10.0.0.1:5000":           "10.0.0.1",
		"[::ffff:10.0.0.1]:5000":  "10.0.0.1",
		"[fd7a:115c::1]:5000":     "fd7a:115c::1",
		"[fe80::1%eth0]:5000":     "fe80::1%eth0",
		"100.101.102.103:65535":   "100.101.102.103",
		"[::ffff:100.64.0.9]:443": "100.64.0.9",
	}
	for addr, want := range valid {
		ctx := metadata.NewIncomingContext(context.Background(), metadata.Pairs(callerHeader, addr))
		got, err := callerIp(ctx)
		if err != nil || got != want {
			t.Errorf("callerIp() of %q = %q, %v, want %q", addr, got, err, want)
		}
	}
	ctx := metadata.NewIncomingContext(context.Background(), metadata.Pairs(callerHeader, "@"))
	if _, err := callerIp(ctx); status.Code(err) != codes.InvalidArgument {
		t.Errorf("callerIp() of a unix address = %v, want InvalidArgument", err)
	}
	if _, err := callerIp(context.Background()); status.Code(err) != codes.Internal {
		t.Errorf("callerIp() without an address = %v, want Internal", err)
	}
}

// fakeServerStream is a server stream that only has a context.
type fakeServerStream struct {
	grpc.ServerStream
	ctx context.Context
}

func (s *fakeServerStream) Context() context.Context { return s.ctx }

// TestCallerInterceptor checks that the caller interceptor records the
// address of the peer, unwrapping coded addresses, and replaces any address
// a caller claims.
func TestCallerInterceptor(t *testing.T) {
	interceptor := newCallerInterceptor()
	peerAddr := &listener.Addr{Addr: &net.TCPAddr{IP: net.IPv4(100, 64, 0, 2), Port: 4000}, Code: listener.ExternalCode}
	ctx := peer.NewContext(context.Background(), &peer.Peer{Addr: peerAddr})
	// The caller claims to be another daemon
	ctx = metadata.NewIncomingContext(ctx, metadata.Pairs(callerHeader, "100.64.0.1:9000", "other", "kept"))
	var got context.Context
	err := interceptor(nil, &fakeServerStream{ctx: ctx}, &grpc.StreamServerInfo{}, func(_ any, ss grpc.ServerStream) error {
		got = ss.Context()
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	ip, err := callerIp(got)
	if err != nil || ip != "100.64.0.2" {
		t.Errorf("callerIp() = %q, %v, want the peer's IP", ip, err)
	}
	md, _ := metadata.FromIncomingContext(got)
	if v := md.Get(callerHeader); len(v) != 1 {
		t.Errorf("caller addresses = %v, want only the peer's", v)
	}
	if v := md.Get("other"); !slices.Equal(v, []string{"kept"}) {
		t.Errorf("other metadata = %v, want it kept", v)
	}
	// The original metadata isn't modified
	orig, _ := metadata.FromIncomingContext(ctx)
	if v := orig.Get(callerHeader); !slices.Equal(v, []string{"100.64.0.1:9000"}) {
		t.Errorf("original metadata modified to %v", v)
	}
}
