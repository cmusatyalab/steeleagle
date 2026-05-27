package util_test

import (
	"context"
	"net"
	"testing"
    "fmt"
	"time"

	"google.golang.org/grpc/peer"
	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	health_pb "google.golang.org/grpc/health/grpc_health_v1"
	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestAuthCode(t *testing.T) {
	lnFile, clientFile, err := util.CreateSocketPairFiles()
	if err != nil {
		t.Errorf("couldn't create socket pairs: %v", err)
	}
	ln, conn, err := util.CreateSocketPairEndpoints(util.MissionCode, lnFile, clientFile)
	if err != nil {
		t.Errorf("couldn't create endpoints: %v", err)
	}
	lnFile.Close()
	clientFile.Close()

    // Define a mock auth interceptor
    authInt := func(
		ctx context.Context,
		req interface{},
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (interface{}, error) {
        p, ok := peer.FromContext(ctx)
        if !ok {
            return nil, fmt.Errorf("couldn't get peer from context")
        }
        a, ok := p.Addr.(*util.Addr)
        if !ok {
            return nil, fmt.Errorf("couldn't get auth code from peer")
        }
        if a.Code != util.MissionCode {
            return nil, fmt.Errorf("cannot call this RPC without code: mission")
        }
		return handler(ctx, req)
	}

	server := grpc.NewServer(grpc.ChainUnaryInterceptor(authInt))
	defer server.GracefulStop()
	health_pb.RegisterHealthServer(server, health.NewServer())
	go server.Serve(ln)

	client := health_pb.NewHealthClient(conn)
	_, err = client.Check(context.Background(), &health_pb.HealthCheckRequest{})
	if err != nil {
		t.Errorf("rpc failed when it was expected to succeed: %v", err)
	}
}

func TestSocketPair(t *testing.T) {
	lnFile, clientFile, err := util.CreateSocketPairFiles()
	if err != nil {
		t.Errorf("couldn't create socket pairs: %v", err)
	}
	ln, conn, err := util.CreateSocketPairEndpoints(util.AdminCode, lnFile, clientFile)
	if err != nil {
		t.Errorf("couldn't create endpoints: %v", err)
	}
	lnFile.Close()
	clientFile.Close()

	server := grpc.NewServer()
	defer server.GracefulStop()
	health_pb.RegisterHealthServer(server, health.NewServer())
	go server.Serve(ln)

	client := health_pb.NewHealthClient(conn)
	_, err = client.Check(context.Background(), &health_pb.HealthCheckRequest{})
	if err != nil {
		t.Errorf("rpc failed when it was expected to succeed: %v", err)
	}
}

func TestACL(t *testing.T) {
	base, err := net.Listen("tcp", "127.0.0.1:8080")
	if err != nil {
		t.Errorf("couldn't listen on localhost port 8080")
	}
	defer base.Close()

	lis := newSpoofedListener(t, base)
	allowed := []string{"100.64.0.0/10"}
	aclLn := util.NewCodedListener(lis, util.ServerCode, util.GetACL(allowed))
	defer aclLn.Close()

	accepted := make(chan net.Conn)
	go func() {
		for {
			conn, err := aclLn.Accept()
			if err != nil {
				return
			}
			accepted <- conn
		}
	}()

	// Rejected case, will be accepted and then closed
	lis.SetFakeIP("101.64.0.1")
	client1, _ := net.Dial("tcp", lis.Addr().String())
	if !isConnClosed(t, client1) {
		t.Errorf("connection 101.64.0.1 should have been rejected, but was accepted")
	}
	client1.Close()

	// Allowed case
	lis.SetFakeIP("100.120.16.5")
	client2, _ := net.Dial("tcp", lis.Addr().String())
	select {
	case conn := <-accepted:
		if isConnClosed(t, conn) {
			t.Errorf("allowed connection rejected incorrectly")
		}
		conn.Close()
	case <-time.After(1 * time.Second):
		t.Errorf("timed out waiting for allowed connection")
	}
	client2.Close()
}
