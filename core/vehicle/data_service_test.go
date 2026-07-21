package vehicle

import (
	"context"
	"fmt"
	"net"
	"path/filepath"
	"testing"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// grpcStatusCode extracts the gRPC status code from err, if any.
func grpcStatusCode(err error) codes.Code {
	return status.Code(err)
}

// streamWaitTimeout bounds how long tests wait for a message to arrive over
// a streaming RPC before failing.
const streamWaitTimeout = time.Second

func newTestDataService(t *testing.T) *DataService {
	t.Helper()
	return &DataService{store: newTestDataStore(t)}
}

// newTestDataServiceClient starts a real gRPC server backed by svc on a unix
// socket and returns a client connected to it. The server and connection are
// torn down automatically when the test ends.
func newTestDataServiceClient(t *testing.T, svc *DataService) vehiclepb.DataServiceClient {
	t.Helper()

	sock := filepath.Join(t.TempDir(), "data-service.sock")
	ln, err := net.Listen("unix", sock)
	if err != nil {
		t.Fatalf("couldn't listen: %v", err)
	}

	server := grpc.NewServer()
	vehiclepb.RegisterDataServiceServer(server, svc)
	go server.Serve(ln)
	t.Cleanup(server.GracefulStop)

	conn, err := grpc.NewClient(
		fmt.Sprintf("unix://%s", sock),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("couldn't dial data service: %v", err)
	}
	t.Cleanup(func() { conn.Close() })

	return vehiclepb.NewDataServiceClient(conn)
}

func TestGetResultUnavailable(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)

	resp, err := client.GetResult(t.Context(), &vehiclepb.GetResultRequest{Name: "producer"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Result != nil {
		t.Fatal("expected result to be nil")
	}
}

func TestGetResult(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)
	res := &resultpb.ComputeResult{Timestamp: timestamppb.Now()}
	svc.store.addResult("producer", res)

	resp, err := client.GetResult(t.Context(), &vehiclepb.GetResultRequest{Name: "producer"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !proto.Equal(resp.Result, res) {
		t.Fatalf("expected %v, got %v", res, resp.Result)
	}
}

func TestGetTelemetryUnavailable(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)

	resp, err := client.GetTelemetry(t.Context(), &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Telemetry != nil {
		t.Fatal("expected result to be nil")
	}
}

func TestGetTelemetry(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)
	tel := &telemetrypb.Telemetry{Timestamp: timestamppb.Now()}
	svc.store.addTelemetry(tel)

	resp, err := client.GetTelemetry(t.Context(), &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !proto.Equal(resp.Telemetry, tel) {
		t.Fatalf("expected %v, got %v", tel, resp.Telemetry)
	}
}

func TestGetFrameUnavailable(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)

	resp, err := client.GetFrame(t.Context(), &vehiclepb.GetFrameRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Frame != nil {
		t.Fatal("expected result to be nil")
	}
}

func TestGetFrame(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)
	frame := &telemetrypb.EncodedFrame{Id: 1}
	svc.store.addFrame(frame)

	resp, err := client.GetFrame(t.Context(), &vehiclepb.GetFrameRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !proto.Equal(resp.Frame, frame) {
		t.Fatalf("expected %v, got %v", frame, resp.Frame)
	}
}

func TestStreamVideoFrames(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)

	ctx, cancel := context.WithCancel(t.Context())
	defer cancel()
	stream, err := client.StreamVideoFrames(ctx, &vehiclepb.StreamVideoFramesRequest{})
	if err != nil {
		t.Fatalf("couldn't open stream: %v", err)
	}

	recvCh := make(chan *vehiclepb.StreamVideoFramesResponse, 1)
	errCh := make(chan error, 1)
	go func() {
		for {
			resp, err := stream.Recv()
			if err != nil {
				errCh <- err
				return
			}
			recvCh <- resp
		}
	}()

	// The server subscribes asynchronously after the RPC arrives, so retry
	// adding a frame until it's received.
	frame := &telemetrypb.EncodedFrame{Id: 1}
	deadline := time.After(streamWaitTimeout)
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()
waitForFrame:
	for {
		select {
		case resp := <-recvCh:
			if !proto.Equal(resp.Frame, frame) {
				t.Fatalf("expected %v, got %v", frame, resp.Frame)
			}
			break waitForFrame
		case err := <-errCh:
			t.Fatalf("unexpected stream error: %v", err)
		case <-ticker.C:
			svc.store.addFrame(frame)
		case <-deadline:
			t.Fatal("timed out waiting for frame")
		}
	}

	cancel()
	select {
	case <-recvCh:
		t.Fatal("expected stream to end after cancellation")
	case err := <-errCh:
		if got := grpcStatusCode(err); got != codes.Canceled {
			t.Fatalf("expected Canceled, got %v (%v)", got, err)
		}
	case <-time.After(streamWaitTimeout):
		t.Fatal("timed out waiting for stream to end")
	}
}

func TestStreamTelemetry(t *testing.T) {
	svc := newTestDataService(t)
	client := newTestDataServiceClient(t, svc)

	ctx, cancel := context.WithCancel(t.Context())
	defer cancel()
	stream, err := client.StreamTelemetry(
		ctx,
		&vehiclepb.StreamTelemetryRequest{},
	)
	if err != nil {
		t.Fatalf("couldn't open stream: %v", err)
	}

	recvCh := make(chan *vehiclepb.StreamTelemetryResponse, 1)
	errCh := make(chan error, 1)
	go func() {
		for {
			resp, err := stream.Recv()
			if err != nil {
				errCh <- err
				return
			}
			recvCh <- resp
		}
	}()

	// The server subscribes asynchronously after the RPC arrives, so retry
	// adding telemetry until it's received.
	tel := &telemetrypb.Telemetry{Timestamp: timestamppb.Now()}
	deadline := time.After(streamWaitTimeout)
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()
waitForTelemetry:
	for {
		select {
		case resp := <-recvCh:
			if !proto.Equal(resp.Telemetry, tel) {
				t.Fatalf("expected %v, got %v", tel, resp.Telemetry)
			}
			break waitForTelemetry
		case err := <-errCh:
			t.Fatalf("unexpected stream error: %v", err)
		case <-ticker.C:
			svc.store.addTelemetry(tel)
		case <-deadline:
			t.Fatal("timed out waiting for telemetry")
		}
	}

	cancel()
	select {
	case <-recvCh:
		t.Fatal("expected stream to end after cancellation")
	case err := <-errCh:
		if got := grpcStatusCode(err); got != codes.Canceled {
			t.Fatalf("expected Canceled, got %v (%v)", got, err)
		}
	case <-time.After(streamWaitTimeout):
		t.Fatal("timed out waiting for stream to end")
	}
}
