package core

import (
    "strings"
    
    "google.golang.org/grpc"
)

type serviceLinks struct {
    control grpc.ClientConn
    mission grpc.ClientConn
}

func (i *serviceLinks) proxyDirector (ctx context.Context, fullMethodName string) (context.Context, *grpc.ClientConn, error) {
    if strings.HasPrefix("Control.") {
        return ctx, serviceLinks.control, nil
    } else if strings.HasPrefix("Mission.") {
        return ctx, serviceLinks.mission, nil
    }
    
    return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
}
