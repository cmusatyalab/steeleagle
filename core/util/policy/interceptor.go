package policy

import (
	"context"
	"fmt"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

// NewPolicyInterceptor creates a gRPC interceptor that monitors commands and checks
// them for access rights against the current policy before forwarding them to the
// end servers.
func (p *Policy) NewPolicyInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
		command := qualifyCommand(ss.Context(), info.FullMethod)
		p.log.Info().Str("command", command).Msg("received RPC request")
		// Check if command is allowed by laws, and transit to new state if necessary
		allowed, _, err := p.SafeCheckAndTransit(ss.Context(), command)
		if allowed == false && err == nil {
			p.log.Error().Str("command", command).Str("state", p.currentState).Msg("command is not allowed in current state")
			return status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, p.currentState)
		} else if allowed == false && err != nil {
			p.log.Warn().Err(err).Msg("policy check failed, denying to be safe")
			return status.Errorf(codes.Internal, "error making policy request, denying to be safe")
		}

		p.log.Info().Str("command", command).Msg("RPC request approved, sending command")
		return handler(srv, ss)
	}
}

// qualifyCommand takes a gRPC command and adds on its AuthCode for policy checking.
func qualifyCommand(ctx context.Context, fullName string) string {
	code := listener.UnknownCode
	// Extract code from the connection address (packed by listener)
	if p, ok := peer.FromContext(ctx); ok {
		if a, ok := p.Addr.(*listener.Addr); ok {
			code = a.Code
		}
	}
	// If code is not available, set to unknown identity
	// Qualify command for law checking
	return fmt.Sprintf("%s%s", code.String(), fullName)
}
