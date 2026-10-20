package router

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net"
	"sync"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/connectivity"
	testgrpc "google.golang.org/grpc/interop/grpc_testing"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// TestResolve ensures that calls resolve to header routes before service
// routes, and that calls with no matching route are Unimplemented.
func TestResolve(t *testing.T) {
	_, addrA := startBackend(t, "a")
	_, addrB := startBackend(t, "b")
	r := newRouter(t, nil, nil)
	if err := r.AddHeaderRoute("vehicle-a", addrA); err != nil {
		t.Fatalf("couldn't add header route: %v", err)
	}
	if err := r.AddServiceRoute("pkg.Service", addrB); err != nil {
		t.Fatalf("couldn't add service route: %v", err)
	}

	withHeader := func(v string) context.Context {
		return metadata.NewIncomingContext(context.Background(), metadata.Pairs(routeHeader, v))
	}
	tests := []struct {
		name   string
		ctx    context.Context
		method string
		want   *grpc.ClientConn
	}{
		{"service", context.Background(), "/pkg.Service/Method", r.services["pkg.Service"]},
		{"header", withHeader("vehicle-a"), "/pkg.Service/Method", r.headers["vehicle-a"]},
		{"header wins over service", withHeader("vehicle-a"), "/other.Service/Method", r.headers["vehicle-a"]},
		{"unknown header falls back to service", withHeader("nope"), "/pkg.Service/Method", r.services["pkg.Service"]},
		{"no route", context.Background(), "/other.Service/Method", nil},
		{"unknown header and no service", withHeader("nope"), "/other.Service/Method", nil},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := r.resolve(tc.ctx, tc.method)
			if tc.want == nil {
				if status.Code(err) != codes.Unimplemented {
					t.Errorf("expected Unimplemented, got conn %v and err %v", got, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tc.want {
				t.Errorf("resolved to wrong conn: got %p, want %p", got, tc.want)
			}
		})
	}
}

// TestResolveGlob ensures that header and service routes match glob
// patterns, with exact keys winning over patterns and longer patterns winning
// over shorter ones.
func TestResolveGlob(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t,
		map[string]string{"vehicle-*": addr, "vehicle-a*": addr, "vehicle-ab": addr},
		map[string]string{"pkg.services.driver.*": addr, "pkg.services.*": addr, "*": addr},
	)

	withHeader := func(v string) context.Context {
		return metadata.NewIncomingContext(context.Background(), metadata.Pairs(routeHeader, v))
	}
	tests := []struct {
		name   string
		ctx    context.Context
		method string
		want   *grpc.ClientConn
	}{
		{"header glob", withHeader("vehicle-z"), "/x.Y/M", r.headers["vehicle-*"]},
		{"longer header glob wins", withHeader("vehicle-abc"), "/x.Y/M", r.headers["vehicle-a*"]},
		{"exact header wins", withHeader("vehicle-ab"), "/x.Y/M", r.headers["vehicle-ab"]},
		{"unmatched header falls back to service", withHeader("drone"), "/pkg.services.driver.Control/M", r.services["pkg.services.driver.*"]},
		{"service glob", context.Background(), "/pkg.services.driver.Control/M", r.services["pkg.services.driver.*"]},
		{"shorter service glob", context.Background(), "/pkg.services.mission.Mission/M", r.services["pkg.services.*"]},
		{"catch-all service glob", context.Background(), "/other.Service/M", r.services["*"]},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := r.resolve(tc.ctx, tc.method)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tc.want {
				t.Errorf("resolved to wrong conn: got %p, want %p", got, tc.want)
			}
		})
	}
}

// TestAddRouteBadPattern ensures that malformed glob patterns are rejected
// and not registered.
func TestAddRouteBadPattern(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, nil)
	if err := r.AddServiceRoute("pkg.[", addr); err == nil {
		t.Errorf("added service route with bad pattern without error")
	}
	if err := r.AddHeaderRoute("key-[", addr); err == nil {
		t.Errorf("added header route with bad pattern without error")
	}
	if len(r.services) != 0 || len(r.headers) != 0 {
		t.Errorf("failed route was still registered")
	}
}

// TestAddRouteOverwriteClosesOld ensures that overwriting a route closes the
// connection it replaces.
func TestAddRouteOverwriteClosesOld(t *testing.T) {
	_, addrA := startBackend(t, "a")
	_, addrB := startBackend(t, "b")
	r := newRouter(t, map[string]string{"key": addrA}, map[string]string{"pkg.*": addrA})
	oldHeader, oldService := r.headers["key"], r.services["pkg.*"]

	if err := r.AddHeaderRoute("key", addrB); err != nil {
		t.Fatalf("couldn't overwrite header route: %v", err)
	}
	if err := r.AddServiceRoute("pkg.*", addrB); err != nil {
		t.Fatalf("couldn't overwrite service route: %v", err)
	}
	if s := oldHeader.GetState(); s != connectivity.Shutdown {
		t.Errorf("old header conn not closed: %v", s)
	}
	if s := oldService.GetState(); s != connectivity.Shutdown {
		t.Errorf("old service conn not closed: %v", s)
	}
	if r.headers["key"].Target() != addrB || r.services["pkg.*"].Target() != addrB {
		t.Errorf("routes not overwritten with new address")
	}
}

// TestAddRouteBadAddress ensures that routes with invalid addresses are
// rejected and not registered.
func TestAddRouteBadAddress(t *testing.T) {
	r := newRouter(t, nil, nil)
	if err := r.AddServiceRoute("pkg.Service", "bogus-scheme://%%%"); err == nil {
		t.Errorf("added service route with bad address without error")
	}
	if err := r.AddHeaderRoute("key", "bogus-scheme://%%%"); err == nil {
		t.Errorf("added header route with bad address without error")
	}
	if len(r.services) != 0 || len(r.headers) != 0 {
		t.Errorf("failed route was still registered")
	}
}

// TestNewRouter ensures that initial routes are registered on creation, nil
// route maps are allowed, and any bad address fails creation.
func TestNewRouter(t *testing.T) {
	_, addrA := startBackend(t, "a")
	_, addrB := startBackend(t, "b")
	r := newRouter(t,
		map[string]string{"vehicle-a": addrA},
		map[string]string{"pkg.Service": addrB, "other.Service": addrA},
	)
	if len(r.headers) != 1 || r.headers["vehicle-a"] == nil {
		t.Errorf("initial header routes not registered: %v", r.headers)
	}
	if len(r.services) != 2 || r.services["pkg.Service"] == nil || r.services["other.Service"] == nil {
		t.Errorf("initial service routes not registered: %v", r.services)
	}

	// Nil maps are allowed and routes can still be added afterwards
	empty := newRouter(t, nil, nil)
	if err := empty.AddServiceRoute("pkg.Service", addrB); err != nil {
		t.Errorf("couldn't add route to router made from nil maps: %v", err)
	}

	// A single bad address fails the whole router
	if _, err := NewRouter(map[string]string{"ok": addrA, "bad": "bogus-scheme://%%%"}, nil); err == nil {
		t.Errorf("created router with bad header address without error")
	}
	if _, err := NewRouter(nil, map[string]string{"bad.Service": "bogus-scheme://%%%"}); err == nil {
		t.Errorf("created router with bad service address without error")
	}
}

// TestUnary ensures that unary calls are proxied to the backend with their
// payload, headers and trailers intact.
func TestUnary(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	body := []byte("hello through the proxy")
	var header, trailer metadata.MD
	resp, err := client.UnaryCall(testContext(t),
		&testgrpc.SimpleRequest{Payload: &testgrpc.Payload{Body: body}},
		grpc.Header(&header), grpc.Trailer(&trailer),
	)
	if err != nil {
		t.Fatalf("unary call failed: %v", err)
	}
	if resp.GetServerId() != "a" {
		t.Errorf("routed to wrong backend: %q", resp.GetServerId())
	}
	if !bytes.Equal(resp.GetPayload().GetBody(), body) {
		t.Errorf("payload mangled: got %q, want %q", resp.GetPayload().GetBody(), body)
	}
	if got := header.Get("x-backend-header"); len(got) != 1 || got[0] != "a" {
		t.Errorf("backend header not forwarded: %v", header)
	}
	if got := trailer.Get("x-backend-trailer"); len(got) != 1 || got[0] != "a" {
		t.Errorf("backend trailer not forwarded: %v", trailer)
	}
}

// TestHeaderRouting ensures that calls are routed by the routing header, and
// fall back to the service route when the header is missing or unknown.
func TestHeaderRouting(t *testing.T) {
	_, addrA := startBackend(t, "a")
	_, addrB := startBackend(t, "b")
	_, addrDefault := startBackend(t, "default")
	r := newRouter(t,
		map[string]string{"a": addrA, "b": addrB},
		map[string]string{testService: addrDefault},
	)
	client := startProxy(t, r)

	for _, tc := range []struct{ key, want string }{
		{"a", "a"},
		{"b", "b"},
		{"unknown", "default"},
		{"", "default"},
	} {
		ctx := testContext(t)
		if tc.key != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, routeHeader, tc.key)
		}
		resp, err := client.UnaryCall(ctx, &testgrpc.SimpleRequest{})
		if err != nil {
			t.Fatalf("call with key %q failed: %v", tc.key, err)
		}
		if resp.GetServerId() != tc.want {
			t.Errorf("key %q routed to %q, want %q", tc.key, resp.GetServerId(), tc.want)
		}
	}
}

// TestMetadataForwarding ensures that caller metadata is forwarded to the
// backend intact, without the routing header or the caller's :authority.
func TestMetadataForwarding(t *testing.T) {
	b, addr := startBackend(t, "a")
	r := newRouter(t, map[string]string{"a": addr}, nil)
	client := startProxy(t, r)

	ctx := metadata.AppendToOutgoingContext(testContext(t),
		routeHeader, "a",
		"x-custom", "one",
		"x-custom", "two",
		"x-bin-bin", string([]byte{0, 1, 2, 255}),
	)
	if _, err := client.UnaryCall(ctx, &testgrpc.SimpleRequest{}); err != nil {
		t.Fatalf("unary call failed: %v", err)
	}

	md := b.metadata()
	if got := md.Get(routeHeader); len(got) != 0 {
		t.Errorf("routing key leaked to backend: %v", got)
	}
	if got := md.Get("x-custom"); len(got) != 2 || got[0] != "one" || got[1] != "two" {
		t.Errorf("multi-value metadata not forwarded intact: %v", got)
	}
	if got := md.Get("x-bin-bin"); len(got) != 1 || got[0] != string([]byte{0, 1, 2, 255}) {
		t.Errorf("binary metadata not forwarded intact: %v", got)
	}
	// The backend sets its own :authority; the caller's must not override it
	if got := md.Get(":authority"); len(got) != 1 || got[0] != addr {
		t.Errorf("caller's :authority forwarded to backend: got %v, want [%s]", got, addr)
	}
}

// TestNoRoute ensures that calls are Unimplemented when the router has no
// routes.
func TestNoRoute(t *testing.T) {
	client := startProxy(t, newRouter(t, nil, nil))
	_, err := client.UnaryCall(testContext(t), &testgrpc.SimpleRequest{})
	if status.Code(err) != codes.Unimplemented {
		t.Errorf("expected Unimplemented, got %v", err)
	}
}

// TestBackendErrorPassthrough ensures that backend error statuses and
// trailers are passed through to the caller.
func TestBackendErrorPassthrough(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	var trailer metadata.MD
	_, err := client.UnaryCall(testContext(t),
		&testgrpc.SimpleRequest{FillUsername: true},
		grpc.Trailer(&trailer),
	)
	s := status.Convert(err)
	if s.Code() != codes.NotFound || s.Message() != "a: not found" {
		t.Errorf("backend status not passed through: %v", err)
	}
	if got := trailer.Get("x-backend-trailer"); len(got) != 1 || got[0] != "a" {
		t.Errorf("backend trailer not forwarded on error: %v", trailer)
	}
}

// TestBackendUnimplementedMethod ensures that a method the backend doesn't
// implement returns the backend's Unimplemented status.
func TestBackendUnimplementedMethod(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	_, err := client.EmptyCall(testContext(t), &testgrpc.Empty{})
	if status.Code(err) != codes.Unimplemented {
		t.Errorf("expected backend's Unimplemented, got %v", err)
	}
}

// TestBackendUnavailable ensures that calls to a backend that isn't listening
// are Unavailable.
func TestBackendUnavailable(t *testing.T) {
	// Grab a free port and close it so nothing is listening
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("couldn't listen on localhost: %v", err)
	}
	addr := lis.Addr().String()
	lis.Close()

	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	_, err = client.UnaryCall(testContext(t), &testgrpc.SimpleRequest{})
	if status.Code(err) != codes.Unavailable {
		t.Errorf("expected Unavailable, got %v", err)
	}
}

// TestServerStreaming ensures that server streams are proxied in order with
// every message intact.
func TestServerStreaming(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	sizes := []int32{0, 1, 10, 1 << 10, 1 << 16, 3}
	req := &testgrpc.StreamingOutputCallRequest{}
	for _, s := range sizes {
		req.ResponseParameters = append(req.ResponseParameters, &testgrpc.ResponseParameters{Size: s})
	}
	stream, err := client.StreamingOutputCall(testContext(t), req)
	if err != nil {
		t.Fatalf("couldn't start stream: %v", err)
	}
	for i, size := range sizes {
		resp, err := stream.Recv()
		if err != nil {
			t.Fatalf("recv %d failed: %v", i, err)
		}
		want := bytes.Repeat([]byte{byte(i)}, int(size))
		if !bytes.Equal(resp.GetPayload().GetBody(), want) {
			t.Errorf("message %d mangled: got %d bytes, want %d", i, len(resp.GetPayload().GetBody()), size)
		}
	}
	if _, err := stream.Recv(); err != io.EOF {
		t.Errorf("expected io.EOF at end of stream, got %v", err)
	}
}

// TestClientStreaming ensures that client streams are proxied with every
// message reaching the backend.
func TestClientStreaming(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	stream, err := client.StreamingInputCall(testContext(t))
	if err != nil {
		t.Fatalf("couldn't start stream: %v", err)
	}
	var want int32
	for i := range 50 {
		body := make([]byte, i*100)
		want += int32(len(body))
		if err := stream.Send(&testgrpc.StreamingInputCallRequest{Payload: &testgrpc.Payload{Body: body}}); err != nil {
			t.Fatalf("send %d failed: %v", i, err)
		}
	}
	resp, err := stream.CloseAndRecv()
	if err != nil {
		t.Fatalf("close and recv failed: %v", err)
	}
	if resp.GetAggregatedPayloadSize() != want {
		t.Errorf("backend saw %d bytes, want %d", resp.GetAggregatedPayloadSize(), want)
	}
}

// TestBidiStreaming ensures that bidirectional streams are proxied in order
// with every message intact while frames flow both ways at once.
func TestBidiStreaming(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	stream, err := client.FullDuplexCall(testContext(t))
	if err != nil {
		t.Fatalf("couldn't start stream: %v", err)
	}

	// Send everything up front so frames are in flight in both directions at
	// once, which is what would expose payload buffers being reused too early.
	const n = 200
	sendErr := make(chan error, 1)
	go func() {
		for i := range n {
			body := []byte(fmt.Sprintf("message-%04d-%s", i, bytes.Repeat([]byte{'x'}, i*37)))
			if err := stream.Send(&testgrpc.StreamingOutputCallRequest{Payload: &testgrpc.Payload{Body: body}}); err != nil {
				sendErr <- err
				return
			}
		}
		sendErr <- stream.CloseSend()
	}()

	for i := range n {
		resp, err := stream.Recv()
		if err != nil {
			t.Fatalf("recv %d failed: %v", i, err)
		}
		want := fmt.Sprintf("message-%04d-%s", i, bytes.Repeat([]byte{'x'}, i*37))
		if string(resp.GetPayload().GetBody()) != want {
			t.Fatalf("message %d mangled: got prefix %.20q, want prefix %.20q", i, resp.GetPayload().GetBody(), want)
		}
	}
	if _, err := stream.Recv(); err != io.EOF {
		t.Errorf("expected io.EOF at end of stream, got %v", err)
	}
	if err := <-sendErr; err != nil {
		t.Errorf("send failed: %v", err)
	}
}

// TestBidiStreamingErrorMidStream ensures that an error status sent by the
// backend partway through a stream is passed through to the caller.
func TestBidiStreamingErrorMidStream(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	stream, err := client.FullDuplexCall(testContext(t))
	if err != nil {
		t.Fatalf("couldn't start stream: %v", err)
	}
	if err := stream.Send(&testgrpc.StreamingOutputCallRequest{Payload: &testgrpc.Payload{Body: []byte("ok")}}); err != nil {
		t.Fatalf("send failed: %v", err)
	}
	if _, err := stream.Recv(); err != nil {
		t.Fatalf("recv failed: %v", err)
	}
	if err := stream.Send(&testgrpc.StreamingOutputCallRequest{
		ResponseStatus: &testgrpc.EchoStatus{Code: int32(codes.FailedPrecondition), Message: "boom"},
	}); err != nil {
		t.Fatalf("send failed: %v", err)
	}
	_, err = stream.Recv()
	s := status.Convert(err)
	if s.Code() != codes.FailedPrecondition || s.Message() != "boom" {
		t.Errorf("backend status not passed through: %v", err)
	}
}

// TestClientCancelPropagates ensures that a caller canceling a call cancels
// the proxied call to the backend.
func TestClientCancelPropagates(t *testing.T) {
	b, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)

	ctx, cancel := context.WithCancel(testContext(t))
	stream, err := client.HalfDuplexCall(ctx)
	if err != nil {
		t.Fatalf("couldn't start stream: %v", err)
	}
	// Wait for the call to reach the backend before cancelling
	deadline := time.Now().Add(5 * time.Second)
	for b.metadata() == nil {
		if time.Now().After(deadline) {
			t.Fatalf("call never reached backend")
		}
		time.Sleep(10 * time.Millisecond)
	}
	cancel()

	done := make(chan error, 1)
	go func() {
		_, err := stream.Recv()
		done <- err
	}()
	select {
	case err := <-done:
		if status.Code(err) != codes.Canceled {
			t.Errorf("expected Canceled, got %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatalf("cancelled call never returned")
	}
}

// TestConcurrentCallsAndRouteUpdates ensures that calls are proxied correctly
// while routes are added concurrently.
func TestConcurrentCallsAndRouteUpdates(t *testing.T) {
	_, addr := startBackend(t, "a")
	r := newRouter(t, nil, map[string]string{testService: addr})
	client := startProxy(t, r)
	ctx := testContext(t)

	var wg sync.WaitGroup
	errs := make(chan error, 64)
	for i := range 32 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			body := []byte(fmt.Sprintf("caller-%d", i))
			resp, err := client.UnaryCall(ctx, &testgrpc.SimpleRequest{Payload: &testgrpc.Payload{Body: body}})
			if err != nil {
				errs <- err
				return
			}
			if !bytes.Equal(resp.GetPayload().GetBody(), body) {
				errs <- fmt.Errorf("caller %d got %q", i, resp.GetPayload().GetBody())
			}
		}()
	}
	// Mutate the routing table while calls are in flight
	for i := range 32 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := r.AddHeaderRoute(fmt.Sprintf("key-%d", i), addr); err != nil {
				errs <- err
			}
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Error(err)
	}
}

// TestRawCodec ensures that the raw codec keeps the proto content-type, only
// handles frames, and copies payloads on unmarshal.
func TestRawCodec(t *testing.T) {
	c := rawCodec{}
	if c.Name() != "proto" {
		t.Errorf("codec name must be proto to keep content-type, got %q", c.Name())
	}

	out, err := c.Marshal(&frame{payload: []byte("abc")})
	if err != nil || string(out) != "abc" {
		t.Errorf("marshal: got %q, %v", out, err)
	}
	if _, err := c.Marshal("not a frame"); err == nil {
		t.Errorf("marshalled non-frame without error")
	}

	data := []byte("xyz")
	f := &frame{}
	if err := c.Unmarshal(data, f); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	data[0] = 'Q'
	if string(f.payload) != "xyz" {
		t.Errorf("unmarshal aliased the input buffer: got %q", f.payload)
	}
	if err := c.Unmarshal(data, struct{}{}); err == nil {
		t.Errorf("unmarshalled into non-frame without error")
	}
}
