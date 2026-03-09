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
    pb "github.com/cmusatyalab/steeleagle/runtime/protos"
    "go.nanomsg.org/mangos/v3"
	"go.nanomsg.org/mangos/v3/protocol/pub"
	"go.nanomsg.org/mangos/v3/protocol/sub"
    _ "go.nanomsg.org/mangos/v3/transport/all"
)

func TestBasicCommands(t *testing.T) {
    vehicle, err := core.NewVehicle(t.Context(), core.WithTest(), core.WithLogConfig(core.LogConfig{Level: "debug"}))
    if err != nil {
        t.Fatalf("failed to create vehicle: %v", err)
    }
    defer vehicle.Stop()
    
    // Control/Arm
    s := grpc.NewServer()
    pb.RegisterControlServer(s, &controlServer{})

    conn, err := net.Listen("unix", filepath.Join(vehicle.Path, "control", core.ControlSocket))
    if err != nil {
        t.Fatalf("failed to listen on control socket: %v", err)
    }
    go func() {
        s.Serve(conn)
        defer conn.Close()
    }()
	defer s.GracefulStop()
	
    client, err := grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(vehicle.Path, core.MainSocket)),
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

    // Repeat the same test with a streaming call
    ctx, cancel = context.WithTimeout(context.Background(), time.Second)
    defer cancel()

    stream, err := c.TakeOff(ctx, &pb.TakeOffRequest{})
    if err != nil {
        t.Fatalf("couldn't open stream: %v", err)
    }

    msg, err := stream.Recv()
	if err == nil {
		t.Fatalf("expected permission denied, command was allowed")
	} else if status.Code(err) != codes.PermissionDenied {
        t.Fatalf("got incorrect error code %v", status.Code(err))
    } else {
        t.Log("correctly got permission denied")
    }

    // Add correct identity (expect success)
	ctx, cancel = context.WithTimeout(context.Background(), time.Second)
    ctx = metadata.NewOutgoingContext(ctx, md)
    defer cancel()

    stream, err = c.TakeOff(ctx, &pb.TakeOffRequest{})

    msg, err = stream.Recv()
    if err != nil || msg.Status != 1 {
        t.Fatalf("mock service call did not return the expected value (1), instead: (%v)", out.Status)
    }
    msg, err = stream.Recv()
    if err != nil || msg.Status != 2 {
        t.Fatalf("mock service call did not return the expected value (2), instead: (%v)", out.Status)
    }
}

func TestStateTransition(t *testing.T) {
    vehicle, err := core.NewVehicle(t.Context(), core.WithTest(), core.WithLogConfig(core.LogConfig{Level: "debug"}))
    if err != nil {
        t.Fatalf("failed to create vehicle: %v", err)
    }
    defer vehicle.Stop()
    
    // Start the Control and Mission servers
    control := grpc.NewServer()
    pb.RegisterControlServer(control, &controlServer{})

    controlConn, err := net.Listen("unix", filepath.Join(vehicle.Path, "control", core.ControlSocket))
    if err != nil {
        t.Fatalf("failed to listen on control socket: %v", err)
    }
    go func() {
        control.Serve(controlConn)
        defer controlConn.Close()
    }()
	defer control.GracefulStop()

    mission := grpc.NewServer()
    pb.RegisterMissionServer(mission, &missionServer{})

    missionConn, err := net.Listen("unix", filepath.Join(vehicle.Path, "mission", core.MissionSocket))
    if err != nil {
        t.Fatalf("failed to listen on mission socket: %v", err)
    }
    go func() {
        mission.Serve(missionConn)
        defer missionConn.Close()
    }()
	defer mission.GracefulStop()

    // Configure clients
    client, err := grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(vehicle.Path, core.MainSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
    if err != nil {
        t.Fatalf("failed to start gRPC client: %v", err)
    }
    defer client.Close()

    controlClient := pb.NewControlClient(client)
    missionClient := pb.NewMissionClient(client)

    // Send Mission/Start to go into LOCAL mode
    md := metadata.Pairs(
        "identity", "server",
    )
    ctx, cancel := context.WithTimeout(context.Background(), time.Second)
    ctx = metadata.NewOutgoingContext(ctx, md)
    defer cancel()

    out, err := missionClient.Start(ctx, &pb.StartRequest{})
    if err != nil {
        t.Fatalf("encountered error with mock service call: %v", err)
    } else if out.Status != 2 {
        t.Fatalf("mock service call did not return the expected value (2), instead: (%v)", out.Status)
    }

    // Send Arm with internal identity to ensure LOCAL control
    md = metadata.Pairs(
        "identity", "internal",
    )
    ctx, cancel = context.WithTimeout(context.Background(), time.Second)
    ctx = metadata.NewOutgoingContext(ctx, md)
    defer cancel()

    out, err = controlClient.Arm(ctx, &pb.ArmRequest{})
    if err != nil {
        t.Fatalf("encountered error with mock service call: %v", err)
    } else if out.Status != 2 {
        t.Fatalf("mock service call did not return the expected value (2), instead: (%v)", out.Status)
    }

    // Send Stop with internal identity to ensure LOCAL control boundaries
    md = metadata.Pairs(
        "identity", "internal",
    )
    ctx, cancel = context.WithTimeout(context.Background(), time.Second)
    ctx = metadata.NewOutgoingContext(ctx, md)
    defer cancel()

    out, err = missionClient.Stop(ctx, &pb.StopRequest{})
	if err == nil {
		t.Fatalf("expected permission denied, command was allowed")
	} else if status.Code(err) != codes.PermissionDenied {
        t.Fatalf("got incorrect error code %v", status.Code(err))
    } else {
        t.Log("correctly got permission denied")
    }

    // Send Stop with server identity to transition back to REMOTE control
    md = metadata.Pairs(
        "identity", "server",
    )
    ctx, cancel = context.WithTimeout(context.Background(), time.Second)
    ctx = metadata.NewOutgoingContext(ctx, md)
    defer cancel()

    out, err = missionClient.Stop(ctx, &pb.StopRequest{})
    if err != nil {
        t.Fatalf("encountered error with mock service call: %v", err)
    } else if out.Status != 2 {
        t.Fatalf("mock service call did not return the expected value (2), instead: (%v)", out.Status)
    }

    // Send Arm with internal identity to ensure REMOTE control boundaries
    md = metadata.Pairs(
        "identity", "internal",
    )
    ctx, cancel = context.WithTimeout(context.Background(), time.Second)
    ctx = metadata.NewOutgoingContext(ctx, md)
    defer cancel()

    out, err = controlClient.Arm(ctx, &pb.ArmRequest{})
	if err == nil {
		t.Fatalf("expected permission denied, command was allowed")
	} else if status.Code(err) != codes.PermissionDenied {
        t.Fatalf("got incorrect error code %v", status.Code(err))
    } else {
        t.Log("correctly got permission denied")
    }
}

func TestDataplane(t *testing.T) {
    vehicle, err := core.NewVehicle(t.Context(), core.WithTest(), core.WithLogConfig(core.LogConfig{Level: "debug"}))
    if err != nil {
        t.Fatalf("failed to create vehicle: %v", err)
    }
    defer vehicle.Stop()

    frontend := fmt.Sprintf("ipc://%s", filepath.Join(vehicle.Path, core.DataInSocket))
    backend := fmt.Sprintf("ipc://%s", filepath.Join(vehicle.Path, core.DataOutSocket))
    testSender, err := pub.NewSocket() 
    if err != nil {
        t.Fatalf("failed to open publisher test socket: %v", err)
    }
    if testSender.Dial(frontend); err != nil {
        t.Fatalf("failed to dial data in socket: %v", err)
    }
    defer testSender.Close()
    
    testReceiver, err := sub.NewSocket() 
    if err != nil {
        t.Fatalf("failed to open subscriber test socket: %v", err)
    }
    if testReceiver.SetOption(mangos.OptionSubscribe, []byte("test")); err != nil {
        t.Fatalf("failed to subcribe to test topic: %v", err)
    }
    if err = testReceiver.Dial(backend); err != nil {
        t.Fatalf("failed to dial data out socket: %v", err)
    }
    defer testReceiver.Close()

    payload := "test" + " " + "helloworld"
    if err = testSender.Send([]byte(payload)); err != nil {
		t.Fatalf("publisher send error: %v", err)
	}

    received, err := testReceiver.Recv()
    if err != nil {
		t.Fatalf("subscriber could not receive: %v", err)
	}

    if string(received) != payload {
        t.Fatalf("received data did not match!")
    }
}
