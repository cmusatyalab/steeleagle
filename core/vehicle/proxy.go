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
			if v.driver == nil {
				return nil, nil, status.Errorf(codes.Unavailable, "no driver plugin configured for this vehicle")
			}
			return ctx, v.driver, nil
		} else if strings.Contains(method, ".MissionService/") {
			if v.mission == nil {
				return nil, nil, status.Errorf(codes.Unimplemented, "no mission plugin configured for this vehicle")
			}
			return ctx, v.mission, nil
		}
		return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
	}
}
