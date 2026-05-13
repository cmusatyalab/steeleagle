package util

import (
	"context"
	"fmt"
	"net"
	"sync"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func NewSocketPairClient(c net.Conn, opts ...grpc.DialOption) (*grpc.ClientConn, error) {
	var once sync.Once
	opts = append(opts,
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			var conn net.Conn
			once.Do(func() { conn = c })
			if conn != nil {
				return conn, nil
			}
			return nil, fmt.Errorf("socketpair connection already used")
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	return grpc.NewClient("passthrough://ignored", opts...)
}
