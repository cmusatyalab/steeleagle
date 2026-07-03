package vehicle_test

import (
	"context"
	"net"
	"testing"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"
)

const (
	bufConnSize = 1 << 20
)

func newMockDriverConn(t *testing.T, streamURL string) (*grpc.ClientConn, error) {
	lis := bufconn.Listen(bufConnSize)
	s := grpc.NewServer()
	driver_pb.RegisterStreamServiceServer(s, &mockStreamSvc{url: streamURL, t: t})
	go s.Serve(lis)
	t.Cleanup(s.Stop)

	conn, _ := grpc.NewClient("passthrough:///bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return lis.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	t.Cleanup(func() { conn.Close() })

	return conn, nil
}

type mockStreamSvc struct {
	driver_pb.UnimplementedStreamServiceServer
	url string
	t   *testing.T
}

func (s *mockStreamSvc) GetVideoStreamURL(ctx context.Context, req *driver_pb.GetVideoStreamURLRequest) (*driver_pb.GetVideoStreamURLResponse, error) {
	s.t.Log("mock stream service received request for video stream URL")
	resp := driver_pb.GetVideoStreamURLResponse{StreamUrl: s.url}
	return &resp, nil
}
