package vehicle

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"

	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

func (v *Vehicle) getLocalProxyDirector() proxy.StreamDirector {
	return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
		if strings.Contains(method, ".ControlService/") {
			return ctx, v.connections.control, nil
		} else if strings.Contains(method, ".MissionService/") {
			return ctx, v.connections.mission, nil
		}
		return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
	}
}

func (v *Vehicle) getGlobalProxyDirector() proxy.StreamDirector {
	conn, err := grpc.NewClient(fmt.Sprintf("unix://%s", filepath.Join(v.path, MainSocket)),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.Fatal().Err(err).Msg("failed to connect to main socket")
	}
	return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
		return ctx, conn, nil
	}
}
