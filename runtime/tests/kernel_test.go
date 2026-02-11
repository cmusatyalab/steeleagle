package test

import (
    "fmt"
    "testing"
    "context"
    "time"
    "path/filepath"
    "net"

    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "google.golang.org/grpc/metadata"
    "google.golang.org/grpc/credentials/insecure"
    "github.com/cmusatyalab/steeleagle/runtime/core"
    "github.com/cmusatyalab/steeleagle/runtime/pb"
)

func TestBasicStartup(t *testing.T) {
    kernel, err := core.NewKernel(t.Context(), core.WithTest(true), core.WithPort(8000))
    defer kernel.Stop()
    if err != nil {
        t.Fatalf("failed to create kernel: %v", err)
    }
    
    // Control/Arm
    s := grpc.NewServer()
    pb.RegisterControlServer(s, &controlServer{})

    conn, err := net.Listen("unix", filepath.Join(kernel.Path, "control", core.ControlSocket))
    if err != nil {
        t.Fatalf("failed to listen on control socket: %v", err)
    }
    go func() {
        e := s.Serve(conn)
        if e != nil {
            conn.Close()
        }
    }()
	defer s.GracefulStop()
	
    client, err := grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(kernel.Path, core.MainSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
    if err != nil {
        t.Fatalf("failed to start gRPC client: %v", err)
    }
    defer client.Close()

    c := pb.NewControlClient(client)

	// Contact the server without manually setting our identity (expect failure)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
    defer cancel()

	out, err := c.Arm(ctx, &pb.ArmRequest{})
	if err == nil {
		t.Fatalf("expected permission denied, command was allowed")
	} else if status.Code(err) != codes.PermissionDenied {
        t.Fatalf("got incorrect error code %v", status.Code(err))
    } else {
        t.Log("correctly got permission denied")
    }

    // Add correct identity (expect success)
    md := metadata.Pairs(
        "identity", "server",
    )
	ctx, cancel = context.WithTimeout(context.Background(), time.Second)
    ctx = metadata.NewOutgoingContext(ctx, md)
    defer cancel()

	out, err = c.Arm(ctx, &pb.ArmRequest{})
    if err != nil {
        t.Fatalf("encountered error with mock service call: %v", err)
    } else if out.Status != 2 {
        t.Fatalf("mock service call did not return the expected value (2), instead: (%v)", out.Status)
    }
}

func TestPolicy(t *testing.T) {}

func TestProxy(t *testing.T) {}

func TestErrorHandling(t *testing.T) {}
