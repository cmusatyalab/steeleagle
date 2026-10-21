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

// NewStreamPolicyInterceptor creates a gRPC stream interceptor that monitors
// commands and checks them for access rights against the current policy before
// forwarding them to the end servers.
func (p *Policy) NewStreamPolicyInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
		if err := p.authorize(ss.Context(), info.FullMethod); err != nil {
			return err
		}
		return handler(srv, ss)
	}
}

// NewUnaryPolicyInterceptor creates a gRPC unary interceptor that applies the
// same policy checks as NewStreamPolicyInterceptor.
func (p *Policy) NewUnaryPolicyInterceptor() grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (any, error) {
		if err := p.authorize(ctx, info.FullMethod); err != nil {
			return nil, err
		}
		return handler(ctx, req)
	}
}

// authorize checks if the command is allowed by laws, and transits to a new
// state if necessary. It returns a gRPC status error if the command is denied.
func (p *Policy) authorize(ctx context.Context, fullMethod string) error {
	command := qualifyCommand(ctx, fullMethod)
	p.log.Info().Str("command", command).Msg("received RPC request")
	allowed, state, err := p.SafeCheckAndTransit(ctx, command)
	if err != nil {
		p.log.Warn().Err(err).Msg("policy check failed, denying to be safe")
		return status.Errorf(codes.Internal, "error making policy request, denying to be safe")
	} else if !allowed {
		p.log.Error().Str("command", command).Str("state", state).Msg("command is not allowed in current state")
		return status.Errorf(codes.PermissionDenied, "command %s is not allowed in state %s", command, state)
	}

	p.log.Info().Str("command", command).Msg("RPC request approved, sending command")
	return nil
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
