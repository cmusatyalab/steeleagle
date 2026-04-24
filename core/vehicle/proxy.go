package vehicle

import (
    "fmt"
    "path/filepath"
    "strings"
    "context"
    
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "github.com/mwitkow/grpc-proxy/proxy"
)

func (i *Vehicle) getLocalProxyDirector() proxy.StreamDirector {
    return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
        if strings.Contains(method, ".ControlService/") {
            return ctx, i.connections.control, nil
        } else if strings.Contains(method, ".MissionService/") {
            return ctx, i.connections.mission, nil
        }
        
        return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
    }
}

func (i *Vehicle) getGlobalProxyDirector() proxy.StreamDirector {
    return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
        conn, err := grpc.DialContext(ctx, fmt.Sprintf("unix://%s", filepath.Join(i.path, MainSocket)),
            grpc.WithTransportCredentials(insecure.NewCredentials()),
        )
        return ctx, conn, err
    }
}
