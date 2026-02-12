package core

import (
    "fmt"
    "context"
    "net"
    "strings"

	"google.golang.org/grpc"
    "google.golang.org/grpc/peer"
    "google.golang.org/grpc/metadata"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func getPeer(ctx context.Context) string {
	p, ok := peer.FromContext(ctx)
	if !ok || p.Addr == nil {
		return "unknown"
	}

	switch addr := p.Addr.(type) {
	case *net.TCPAddr:
		if addr.IP.IsLoopback() {
			return "internal"
		}
		return "server"
	case *net.UnixAddr:
		return "internal"
	default:
		if addr.Network() == "pipe" {
            return "kernel"
        } else {
            return "unknown"
        }
	}
}

func cleanCommand(ctx context.Context, fullName string, isTesting bool) string {
    // If we are in test mode, we can set our peer type to test the policy
    peer := "unknown"
    if isTesting {
        md, ok := metadata.FromIncomingContext(ctx)
        if !ok {
            peer = getPeer(ctx)
        } else if identity, exists := md["identity"]; exists {
            if len(identity) > 0 {
                peer = identity[0]
            } else {
                peer = getPeer(ctx)
            }
        }
    } else {
        peer = getPeer(ctx)
    }

    splits := strings.Split(fullName, ".")
    return fmt.Sprintf("%s/%s", peer, splits[len(splits) - 1])
}

func (i *policyState) getUnaryInterceptor() grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (any, error) {

        command := cleanCommand(ctx, info.FullMethod, i.test)
        logger.Info("received unary RPC request", "command", command)
		allowed, _, err := i.safeCheckAndTransit(ctx, command)
        if allowed == false && err == nil {
            logger.Error("command is not allowed in current state!", "command", command, "state", i.currentState)
		    return nil, status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, i.currentState)
		} else if allowed == false && err != nil {
            logger.Warn("policy check failed, denying to be safe", "error", err)
            return nil, status.Errorf(codes.Internal, "policy check failed, denying to be safe")
        }

        logger.Info("responding to unary RPC request", "command", command)
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

        command := cleanCommand(ss.Context(), info.FullMethod, i.test)
        logger.Info("received stream RPC request", "command", command)
		allowed, _, err := i.safeCheckAndTransit(ss.Context(), command)
        if allowed == false && err == nil {
            logger.Error("command is not allowed in current state!", "command", command, "state", i.currentState)
		    return status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, i.currentState)
		} else if allowed == false && err != nil {
            logger.Warn("policy check failed, denying to be safe", "error", err)
            return status.Errorf(codes.Internal, "error making policy request, denying to be safe")
        }

        logger.Info("responding to stream RPC request", "command", command)
		return handler(srv, ss)
	}
}
