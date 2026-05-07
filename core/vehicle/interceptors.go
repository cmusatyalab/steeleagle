package vehicle

import (
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func (p *policyState) getWanInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {

	}
}

func (p *policyState) getMissionInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {

	}
}

func (p *policyState) getMainInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
		command := //TODO: Clean the command
			log.Info().Str("command", command).Msg("received RPC request")
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
