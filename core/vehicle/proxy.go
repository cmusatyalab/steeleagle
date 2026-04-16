package vehicle

import (
    "strings"
    "context"
    
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "github.com/mwitkow/grpc-proxy/proxy"
)

func (i *Vehicle) getProxyDirector() proxy.StreamDirector {
    return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
        if strings.Contains(method, ".Control/") {
            return ctx, i.services.control, nil
        } else if strings.Contains(method, ".Mission/") {
            return ctx, i.services.mission, nil
        }
        
        return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
    }
}
