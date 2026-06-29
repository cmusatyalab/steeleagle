package vehicle

import (
	"context"
	"fmt"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

func qualifyCommand(ctx context.Context, fullName string) string {
	var code util.AuthCode
	// Extract code from the connection address (packed by listener)
	var ok bool
	if p, ok := peer.FromContext(ctx); ok {
		if a, ok := p.Addr.(*util.Addr); ok {
			code = a.Code
		}
	}
	// If code is not available, set to unknown identity
	if !ok {
		code = util.UnknownCode
	}
	// Qualify command for law checking
	return fmt.Sprintf("%s%s", code.String(), fullName)
}

func (v *Vehicle) getInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
		command := qualifyCommand(ss.Context(), info.FullMethod)
        // TODO: Add in the logging that was removed from policy
		log.Info().Str("command", command).Msg("received RPC request")
		// Check if command is allowed by laws, and transit to new state if necessary
		allowed, _, err := p.policyState.safeCheckAndTransit(ss.Context(), command)
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
