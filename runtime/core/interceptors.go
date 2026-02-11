package core

import (
    "context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func (i *policyState) getUnaryInterceptor() grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (any, error) {

		allowed, command, err := i.safeCheckAndTransit(ctx, info.FullMethod)
        if allowed == false && err == nil {
		    return nil, status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, i.currentState)
		} else if allowed == false && err != nil {
            return nil, status.Errorf(codes.Internal, "error making policy request, denying to be safe")
        }

		return handler(ctx, req)
	}
}

func (i *policyState) getStreamInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {

		allowed, command, err := i.safeCheckAndTransit(ss.Context(), info.FullMethod)
        if allowed == false && err == nil {
		    return status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, i.currentState)
		} else if allowed == false && err != nil {
            return status.Errorf(codes.Internal, "error making policy request, denying to be safe")
        }

		return handler(srv, ss)
	}
}
