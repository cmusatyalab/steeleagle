package daemon

import (
	"context"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"sync"
	"testing"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

// startRoutingDaemon starts the servers of a daemon whose config.toml holds
// content, with the relay on a local TCP port where every caller has
// ExternalCode. It returns the daemon and the address of its relay.
func startRoutingDaemon(t *testing.T, content string) (*Daemon, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), ConfigFileName)
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		t.Fatal(err)
	}
	d := &Daemon{configPath: path, log: testLogger()}
	if d.policy, err = policy.NewPolicy(law, policy.WithLogger(testLogger())); err != nil {
		t.Fatal(err)
	}
	if err := d.setupRelay(); err != nil {
		t.Fatal(err)
	}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	go d.server.Serve(d.serverLn)
	go d.relay.Serve(listener.NewCodedListener(ln, listener.NewAcl(nil, nil, true), listener.WithLogger(testLogger())))
	t.Cleanup(func() {
		d.relay.Stop()
		d.serverConn.Close()
		d.server.Stop()
	})
	return d, ln.Addr().String()
}

// dial returns a client connection to addr.
func dial(t *testing.T, addr string) *grpc.ClientConn {
	t.Helper()
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

// withRouteKey returns a context for a call routed by key.
func withRouteKey(key string) context.Context {
	return metadata.AppendToOutgoingContext(context.Background(), "x-route-key", key)
}

// TestDaemonServiceRouting ensures that daemon service calls are handled
// locally without a route key, by the remote daemon whose IP is their route
// key, and not at all with an unknown route key, and that the law applies
// before a call is routed.
func TestDaemonServiceRouting(t *testing.T) {
	orchestrator, addr := startRoutingDaemon(t, "[daemon]\nhostname = 'homebase'\n")
	remote, remoteAddr := startRoutingDaemon(t, "[daemon]\nhostname = 'remote'\n")
	orchestrator.router.AddHeaderRoute("100.64.0.7", dial(t, remoteAddr))
	// As registerWithOrchestrator does, the remote routes its own IP to itself
	remote.router.AddHeaderRoute("100.64.0.7", remote.serverConn)
	client := daemonpb.NewDaemonServiceClient(dial(t, addr))

	for key, want := range map[string]string{"": "homebase", "100.64.0.7": "remote"} {
		ctx := context.Background()
		if key != "" {
			ctx = withRouteKey(key)
		}
		resp, err := client.GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
		if err != nil {
			t.Errorf("key %q: get configuration failed: %v", key, err)
			continue
		}
		cfg, err := config.ParseDaemonConfigFromBytes(resp.GetConfigToml())
		if err != nil || cfg.Daemon.Hostname != want {
			t.Errorf("key %q: expected the config of %s, got %q, %v", key, want, resp.GetConfigToml(), err)
		}
	}

	// A call for an unknown daemon is rejected, not handled locally
	if _, err := client.GetConfiguration(withRouteKey("100.64.0.8"), &daemonpb.GetConfigurationRequest{}); status.Code(err) != codes.NotFound {
		t.Errorf("expected NotFound for an unknown key, got %v", err)
	}

	// External callers can't configure the orchestrator, so they can't
	// configure the remote daemon through it either
	if _, err := client.Configure(withRouteKey("100.64.0.7"), &daemonpb.ConfigureRequest{}); status.Code(err) != codes.PermissionDenied {
		t.Errorf("expected PermissionDenied for a routed configure, got %v", err)
	}
}

// fakeTransfers is a remote transfer service that acknowledges each file
// chunk it receives.
type fakeTransfers struct {
	daemonpb.UnimplementedTransferServiceServer
	mu     sync.Mutex
	chunks []string
}

func (f *fakeTransfers) TransferFile(
	stream grpc.BidiStreamingServer[daemonpb.TransferFileRequest, daemonpb.TransferFileResponse],
) error {
	for {
		req, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}
		f.mu.Lock()
		f.chunks = append(f.chunks, string(req.GetChunk()))
		f.mu.Unlock()
		if err := stream.Send(daemonpb.TransferFileResponse_builder{Received: req.GetNumber()}.Build()); err != nil {
			return err
		}
	}
}

// TestTransferRouting ensures that a streamed transfer is routed in full to
// the remote daemon whose IP is its route key, with the remote's responses
// streamed back.
func TestTransferRouting(t *testing.T) {
	orchestrator, addr := startRoutingDaemon(t, "[daemon]\n")
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	remote := &fakeTransfers{}
	server := grpc.NewServer()
	daemonpb.RegisterTransferServiceServer(server, remote)
	go server.Serve(ln)
	t.Cleanup(server.Stop)
	orchestrator.router.AddHeaderRoute("100.64.0.7", dial(t, ln.Addr().String()))

	stream, err := daemonpb.NewTransferServiceClient(dial(t, addr)).TransferFile(withRouteKey("100.64.0.7"))
	if err != nil {
		t.Fatal(err)
	}
	for i, chunk := range []string{"a", "b", "c"} {
		req := daemonpb.TransferFileRequest_builder{Chunk: []byte(chunk), Number: int32(i + 1), Total: 3}.Build()
		if err := stream.Send(req); err != nil {
			t.Fatalf("send failed: %v", err)
		}
	}
	stream.CloseSend()
	var received []int32
	for {
		resp, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			t.Fatalf("transfer failed: %v", err)
		}
		received = append(received, resp.GetReceived())
	}
	if len(received) != 3 || received[0] != 1 || received[2] != 3 {
		t.Errorf("expected all 3 chunks acknowledged, got %v", received)
	}
	if len(remote.chunks) != 3 || remote.chunks[0] != "a" || remote.chunks[2] != "c" {
		t.Errorf("expected the remote to get chunks a, b, c, got %v", remote.chunks)
	}
}

// TestCallerInterceptor ensures that the caller address recorded for the
// daemon services is the address of the peer, replacing any the caller sent.
func TestCallerInterceptor(t *testing.T) {
	addr := &listener.Addr{Addr: &net.TCPAddr{IP: net.ParseIP("100.64.0.7"), Port: 41234}, Code: listener.ExternalCode}
	ctx := peer.NewContext(context.Background(), &peer.Peer{Addr: addr})
	ctx = metadata.NewIncomingContext(ctx, metadata.Pairs(callerHeader, "100.64.0.9:1", "x-custom", "kept"))

	var got context.Context
	handler := func(srv any, stream grpc.ServerStream) error {
		got = stream.Context()
		return nil
	}
	if err := callerInterceptor(nil, &fakeStream{ctx: ctx}, &grpc.StreamServerInfo{}, handler); err != nil {
		t.Fatal(err)
	}
	ip, err := callerIp(got)
	if err != nil || ip.String() != "100.64.0.7" {
		t.Errorf("expected caller 100.64.0.7, got %v, %v", ip, err)
	}
	md, _ := metadata.FromIncomingContext(got)
	if v := md.Get(callerHeader); len(v) != 1 {
		t.Errorf("expected one caller address, got %v", v)
	}
	if v := md.Get("x-custom"); len(v) != 1 || v[0] != "kept" {
		t.Errorf("expected other metadata kept, got %v", v)
	}
}

// fakeStream is a minimal grpc.ServerStream that only supplies a context.
type fakeStream struct {
	grpc.ServerStream
	ctx context.Context
}

// Context returns the context supplied to the fake stream.
func (s *fakeStream) Context() context.Context {
	return s.ctx
}
