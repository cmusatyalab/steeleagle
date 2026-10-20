package router

import (
	"context"
	"fmt"
	"io"
	"os"
	"path"
	"strings"
	"sync"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// routeHeader is the metadata key for header routing.
const routeHeader = "x-route-key"

// Router is a proxy router that sends messages to the correct backend
// by header (uses "x-route-key" as the routing key) or by service if
// no header is provided. Route keys are glob patterns (see path.Match),
// so "pkg.*" matches every service in package pkg. An exact key always
// wins, then the longest matching pattern.
type Router struct {
	mu       sync.RWMutex                // mutex for atomic updates
	headers  map[string]*grpc.ClientConn // x-route-key value pattern
	services map[string]*grpc.ClientConn // "pkg.Service" pattern
	log      zerolog.Logger              // logger object
}

// NewRouter creates a Router, optionally seeded with header routes
// (x-route-key value -> address) and service routes ("pkg.Service" -> address).
// Either map may be nil.
func NewRouter(headers, services map[string]string, opts ...RouterOption) (*Router, error) {
	r := &Router{
		headers:  map[string]*grpc.ClientConn{},
		services: map[string]*grpc.ClientConn{},
		log:      zerolog.New(os.Stdout).With().Timestamp().Logger(),
	}
	for _, opt := range opts {
		opt(r)
	}
	for header, address := range headers {
		if err := r.AddHeaderRoute(header, address); err != nil {
			r.Close()
			return nil, err
		}
	}
	for service, address := range services {
		if err := r.AddServiceRoute(service, address); err != nil {
			r.Close()
			return nil, err
		}
	}
	return r, nil
}

// Close closes every backend connection held by the router.
func (r *Router) Close() {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, c := range r.headers {
		c.Close()
	}
	for _, c := range r.services {
		c.Close()
	}
}

// AddHeaderRoute adds a new header-based routing rule. The header may be a
// glob pattern. Overwriting an existing route closes its old connection.
func (r *Router) AddHeaderRoute(header, address string) error {
	if _, err := path.Match(header, ""); err != nil {
		return fmt.Errorf("bad header pattern %q: %w", header, err)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	c, err := grpc.NewClient(address,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(grpc.ForceCodec(rawCodec{})),
	)
	if err != nil {
		return err
	}
	if old, ok := r.headers[header]; ok {
		old.Close()
	}
	r.headers[header] = c
	r.log.Debug().Str("header", header).Str("addr", address).Msg("adding header route")
	return nil
}

// AddServiceRoute adds a new service-based routing rule. The service may be a
// glob pattern. Overwriting an existing route closes its old connection.
func (r *Router) AddServiceRoute(service, address string) error {
	if _, err := path.Match(service, ""); err != nil {
		return fmt.Errorf("bad service pattern %q: %w", service, err)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	c, err := grpc.NewClient(address,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(grpc.ForceCodec(rawCodec{})),
	)
	if err != nil {
		return err
	}
	if old, ok := r.services[service]; ok {
		old.Close()
	}
	r.services[service] = c
	r.log.Debug().Str("service", service).Str("addr", address).Msg("adding service route")
	return nil
}

// resolve gets the gRPCClientConn for a gRPC call.
func (r *Router) resolve(ctx context.Context, fullMethod string) (*grpc.ClientConn, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	md, _ := metadata.FromIncomingContext(ctx)
	if v := md.Get(routeHeader); len(v) > 0 {
		if c, ok := match(r.headers, v[0]); ok {
			r.log.Debug().Str("method", fullMethod).Str("addr", c.Target()).Msg("dispatching method")
			return c, nil
		}
	}
	// fullMethod looks like "/pkg.Service/Method"
	svc := strings.SplitN(strings.TrimPrefix(fullMethod, "/"), "/", 2)[0]
	if c, ok := match(r.services, svc); ok {
		r.log.Debug().Str("method", fullMethod).Str("addr", c.Target()).Msg("dispatching method")
		return c, nil
	}
	// Reject if there is no recognized header key or service
	r.log.Error().Str("method", fullMethod).Msg("no route for method")
	return nil, status.Errorf(codes.Unimplemented, "no route for %s", fullMethod)
}

// match finds the route for key, preferring an exact key and then the longest
// matching pattern (ties broken alphabetically so the choice is stable).
func match(routes map[string]*grpc.ClientConn, key string) (*grpc.ClientConn, bool) {
	if c, ok := routes[key]; ok {
		return c, true
	}
	var best string
	var found *grpc.ClientConn
	for pattern, c := range routes {
		if ok, _ := path.Match(pattern, key); !ok {
			continue
		}
		if found == nil || len(pattern) > len(best) || (len(pattern) == len(best) && pattern < best) {
			best, found = pattern, c
		}
	}
	return found, found != nil
}

// handle handles a gRPC call.
func (r *Router) handle(_ any, down grpc.ServerStream) error {
	fullMethod, ok := grpc.MethodFromServerStream(down)
	if !ok {
		return status.Error(codes.Internal, "no method in stream")
	}
	ctx := down.Context()
	cc, err := r.resolve(ctx, fullMethod)
	if err != nil {
		return err
	}

	// Forward caller metadata, minus pseudo-headers and the routing key
	inMD, _ := metadata.FromIncomingContext(ctx)
	outMD := metadata.MD{}
	for k, v := range inMD {
		if strings.HasPrefix(k, ":") || k == routeHeader {
			continue
		}
		outMD[k] = v
	}
	upCtx, cancel := context.WithCancel(metadata.NewOutgoingContext(ctx, outMD))
	defer cancel()

	// Treat every call as bidi streaming
	desc := &grpc.StreamDesc{ServerStreams: true, ClientStreams: true}
	up, err := cc.NewStream(upCtx, desc, fullMethod)
	if err != nil {
		return err
	}

	downToUp := pumpDownToUp(down, up)
	upToDown := pumpUpToDown(up, down)

	for i := 0; i < 2; i++ {
		select {
		case err := <-downToUp:
			if err == io.EOF {
				// Caller finished sending, tell the backend and keep reading replies
				up.CloseSend()
				continue
			}
			cancel()
			return status.Errorf(codes.Internal, "router: forwarding request: %v", err)
		case err := <-upToDown:
			down.SetTrailer(up.Trailer())
			if err == io.EOF {
				return nil // backend returned OK
			}
			return err // backend's status (code + message) passes through
		}
	}
	return status.Error(codes.Internal, "router: unreachable")
}

// pumpDownToUp empties the gRPC stream upstream.
func pumpDownToUp(src grpc.ServerStream, dst grpc.ClientStream) <-chan error {
	ch := make(chan error, 1)
	go func() {
		f := &frame{}
		for {
			if err := src.RecvMsg(f); err != nil {
				ch <- err // io.EOF when the caller half-closes
				return
			}
			if err := dst.SendMsg(f); err != nil {
				ch <- err
				return
			}
		}
	}()
	return ch
}

// pumpUpToDown empties the gRPC stream downstream.
func pumpUpToDown(src grpc.ClientStream, dst grpc.ServerStream) <-chan error {
	ch := make(chan error, 1)
	go func() {
		f := &frame{}
		first := true
		for {
			if err := src.RecvMsg(f); err != nil {
				ch <- err // io.EOF on OK, status error otherwise
				return
			}
			if first {
				// Headers are only available after the first response
				first = false
				md, err := src.Header()
				if err != nil {
					ch <- err
					return
				}
				if err := dst.SendHeader(md); err != nil {
					ch <- err
					return
				}
			}
			if err := dst.SendMsg(f); err != nil {
				ch <- err
				return
			}
		}
	}()
	return ch
}
