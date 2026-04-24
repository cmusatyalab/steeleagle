package vehicle

import (
    "fmt"
    "context"
    "net"

	"google.golang.org/grpc"
    "google.golang.org/grpc/peer"
    "google.golang.org/grpc/metadata"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
    "github.com/rs/zerolog/log"
)

type identityMeta struct {
    source      
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

    return fmt.Sprintf("%s%s", peer, fullName)
}

func (i *policyState) getIdentityInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
        command := cleanCommand(ss.Context(), info.FullMethod, isTesting)
        log.Info().Str("command", command).Msg("received RPC request")
		allowed, _, err := i.safeCheckAndTransit(ss.Context(), command)
        if allowed == false && err == nil {
            log.Error().Str("command", command).Str("state", i.currentState).Msg("command is not allowed in current state!")
		    return status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, i.currentState)
		} else if allowed == false && err != nil {
            log.Warn().Err(err).Msg("policy check failed, denying to be safe")
            return status.Errorf(codes.Internal, "error making policy request, denying to be safe")
        }

        log.Info().Str("command", command).Msg("responding to RPC request")
		return handler(srv, ss)
	}
}
