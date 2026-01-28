package core

import (
    "context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func (i *policyState) unaryInterceptor() grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (any, error) {

		allowed, err := i.safeCheckAndTransit(ctx, info.FullMethod)
        if allowed == false && err == nil {
		    return nil, status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", info.FullMethod, i.state)
		} else if allowed == false && err != nil {
            return nil, status.Errorf(codes.Internal, "error making policy request, denying to be safe"
        }

		return handler(srv, ss)
	}
}

func (i *policyState) streamInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {

		allowed, err := i.safeCheckAndTransit(ctx, info.FullMethod)
        if i.checkPeer(ctx) == false {
            if allowed == false && err == nil {
			    return nil, status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", info.FullMethod, i.state)
		    } else if allowed == false && err != nil {
                return nil, status.Errorf(codes.Internal, "error making policy request, denying to be safe"
            }
        }

		return handler(srv, ss)
	}
}
