package router

import (
	"bytes"
	"context"
	"io"
	"net"
	"sync"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	testgrpc "google.golang.org/grpc/interop/grpc_testing"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

const testService = "grpc.testing.TestService"

// backend is a TestService that tags every response with its name so tests
// can tell which backend a call was routed to.
type backend struct {
	testgrpc.UnimplementedTestServiceServer
	name string

	mu     sync.Mutex
	lastMD metadata.MD // incoming metadata of the most recent call
}

// record stores the incoming metadata of a call.
func (b *backend) record(ctx context.Context) {
	md, _ := metadata.FromIncomingContext(ctx)
	b.mu.Lock()
	b.lastMD = md
	b.mu.Unlock()
}

// metadata returns the incoming metadata of the most recent call.
func (b *backend) metadata() metadata.MD {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.lastMD
}

// UnaryCall echoes the request payload, and fails if FillUsername is set.
func (b *backend) UnaryCall(ctx context.Context, req *testgrpc.SimpleRequest) (*testgrpc.SimpleResponse, error) {
	b.record(ctx)
	grpc.SetHeader(ctx, metadata.Pairs("x-backend-header", b.name))
	grpc.SetTrailer(ctx, metadata.Pairs("x-backend-trailer", b.name))
	if req.GetFillUsername() {
		// Overloaded to mean "fail", so error passthrough can be tested
		return nil, status.Errorf(codes.NotFound, "%s: not found", b.name)
	}
	return &testgrpc.SimpleResponse{
		Payload:  req.GetPayload(),
		ServerId: b.name,
	}, nil
}

// StreamingOutputCall sends one message of each requested size.
func (b *backend) StreamingOutputCall(req *testgrpc.StreamingOutputCallRequest, stream grpc.ServerStreamingServer[testgrpc.StreamingOutputCallResponse]) error {
	b.record(stream.Context())
	for i, p := range req.GetResponseParameters() {
		body := bytes.Repeat([]byte{byte(i)}, int(p.GetSize()))
		if err := stream.Send(&testgrpc.StreamingOutputCallResponse{
			Payload: &testgrpc.Payload{Body: body},
		}); err != nil {
			return err
		}
	}
	return nil
}

// StreamingInputCall replies with the total payload size received.
func (b *backend) StreamingInputCall(stream grpc.ClientStreamingServer[testgrpc.StreamingInputCallRequest, testgrpc.StreamingInputCallResponse]) error {
	b.record(stream.Context())
	var total int32
	for {
		req, err := stream.Recv()
		if err == io.EOF {
			return stream.SendAndClose(&testgrpc.StreamingInputCallResponse{AggregatedPayloadSize: total})
		}
		if err != nil {
			return err
		}
		total += int32(len(req.GetPayload().GetBody()))
	}
}

// FullDuplexCall echoes every message, and fails with the requested status if
// one is set.
func (b *backend) FullDuplexCall(stream grpc.BidiStreamingServer[testgrpc.StreamingOutputCallRequest, testgrpc.StreamingOutputCallResponse]) error {
	b.record(stream.Context())
	for {
		req, err := stream.Recv()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}
		if s := req.GetResponseStatus(); s != nil {
			return status.Error(codes.Code(s.GetCode()), s.GetMessage())
		}
		if err := stream.Send(&testgrpc.StreamingOutputCallResponse{Payload: req.GetPayload()}); err != nil {
			return err
		}
	}
}

// HalfDuplexCall blocks until the caller goes away, for cancellation tests.
func (b *backend) HalfDuplexCall(stream grpc.BidiStreamingServer[testgrpc.StreamingOutputCallRequest, testgrpc.StreamingOutputCallResponse]) error {
	b.record(stream.Context())
	<-stream.Context().Done()
	return stream.Context().Err()
}

// startBackend serves a named TestService on a random localhost port.
func startBackend(t *testing.T, name string) (*backend, string) {
	t.Helper()
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("couldn't listen on localhost: %v", err)
	}
	b := &backend{name: name}
	s := grpc.NewServer()
	testgrpc.RegisterTestServiceServer(s, b)
	go s.Serve(lis)
	t.Cleanup(s.Stop)
	return b, lis.Addr().String()
}

// newRouter creates a Router that is closed when the test ends.
func newRouter(t *testing.T, headers, services map[string]string) *Router {
	t.Helper()
	r, err := NewRouter(headers, services)
	if err != nil {
		t.Fatalf("couldn't create router: %v", err)
	}
	t.Cleanup(r.Close)
	return r
}

// startProxy serves r on a random localhost port and returns a TestService
// client connected to it.
func startProxy(t *testing.T, r *Router) testgrpc.TestServiceClient {
	t.Helper()
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("couldn't listen on localhost: %v", err)
	}
	s := grpc.NewServer(
		grpc.UnknownServiceHandler(r.handle),
		grpc.ForceServerCodec(rawCodec{}),
	)
	go s.Serve(lis)
	t.Cleanup(s.Stop)

	cc, err := grpc.NewClient(lis.Addr().String(),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("couldn't create proxy client: %v", err)
	}
	t.Cleanup(func() { cc.Close() })
	return testgrpc.NewTestServiceClient(cc)
}

// testContext returns a context with a timeout that is canceled when the test
// ends.
func testContext(t *testing.T) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	t.Cleanup(cancel)
	return ctx
}
