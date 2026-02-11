package core

import (
    "strings"
    "context"
    
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "github.com/mwitkow/grpc-proxy/proxy"
)

func getProxyDirector(control *grpc.ClientConn, mission *grpc.ClientConn) proxy.StreamDirector {
    // The returned function captures control and mission in its closure
    return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
        if strings.Contains(method, ".Control/") {
            return ctx, control, nil
        } else if strings.Contains(method, ".Mission/") {
            return ctx, mission, nil
        }
        
        return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
    }
}
