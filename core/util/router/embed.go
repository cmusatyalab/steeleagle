package router

import (
	"context"

	"google.golang.org/grpc/metadata"
)

// Embed returns a copy of ctx whose outgoing metadata carries key as the
// routing key, replacing any routing key already present.
func Embed(ctx context.Context, key string) context.Context {
	md, _ := metadata.FromOutgoingContext(ctx)
	md = md.Copy()
	md.Set(routeHeader, key)
	return metadata.NewOutgoingContext(ctx, md)
}
