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

func (i *policyState) getUnaryInterceptor(isTesting bool) grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (any, error) {

        command := cleanCommand(ctx, info.FullMethod, isTesting)
        logger.Info().Str("command", command).Msg("received unary RPC request")
		allowed, _, err := i.safeCheckAndTransit(ctx, command)
        if allowed == false && err == nil {
            logger.Error().Str("command", command).Str("state", i.currentState).Msg("command is not allowed in current state!")
		    return nil, status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, i.currentState)
		} else if allowed == false && err != nil {
            logger.Warn().Err(err).Msg("policy check failed, denying to be safe")
            return nil, status.Errorf(codes.Internal, "policy check failed, denying to be safe")
        }

        logger.Info().Str("command", command).Msg("responding to unary RPC request")
		return handler(ctx, req)
	}
}

func (i *policyState) getStreamInterceptor(isTesting bool) grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {

        command := cleanCommand(ss.Context(), info.FullMethod, isTesting)
        logger.Info().Str("command", command).Msg("received stream RPC request")
		allowed, _, err := i.safeCheckAndTransit(ss.Context(), command)
        if allowed == false && err == nil {
            logger.Error().Str("command", command).Str("state", i.currentState).Msg("command is not allowed in current state!")
		    return status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, i.currentState)
		} else if allowed == false && err != nil {
            logger.Warn().Err(err).Msg("policy check failed, denying to be safe")
            return status.Errorf(codes.Internal, "error making policy request, denying to be safe")
        }

        logger.Info().Str("command", command).Msg("responding to stream RPC request")
		return handler(srv, ss)
	}
}
