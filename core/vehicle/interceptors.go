package vehicle

import (
    "fmt"

	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func qualifyCommand(ctx context.Context, fullName string) {
    var code AuthCode
    // Extract code from the connection address (packed by listener)
    if p, ok := peer.FromContext(ctx); ok {
        if a, ok := p.Addr.(*addr); ok {
            code = a.code
        }
    }
    // If code is not available, set to unknown identity
    if !ok {
        code = Unknown
    }
    // Qualify command for law checking
    return fmt.Sprintf("%s%s", code, fullName)
}

func (p *policyState) getInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
		command := qualifyCommand(ss.Context(), info.FullMethod)
		log.Info().Str("command", command).Msg("received RPC request")
        // Check if command is allowed by laws, and transit to new state if necessary
		allowed, _, err := p.safeCheckAndTransit(ss.Context(), command)
		if allowed == false && err == nil {
			log.Error().Str("command", command).Str("state", p.currentState).Msg("command is not allowed in current state!")
			return status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, p.currentState)
		} else if allowed == false && err != nil {
			log.Warn().Err(err).Msg("policy check failed, denying to be safe")
			return status.Errorf(codes.Internal, "error making policy request, denying to be safe")
		}

		log.Info().Str("command", command).Msg("responding to RPC request")
		return handler(srv, ss)
	}
}
