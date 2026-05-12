package vehicle

import (
	"context"
	"strings"

	"github.com/mwitkow/grpc-proxy/proxy"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func (v *Vehicle) getProxyDirector() proxy.StreamDirector {
	return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
		if strings.Contains(method, ".ControlService/") || strings.Contains(method, ".StreamService/") {
			return ctx, v.conns.driver, nil
		} else if strings.Contains(method, ".MissionService/") {
			return ctx, v.conns.mission, nil
		}
		return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
	}
}
