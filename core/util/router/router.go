package router

import (
	"context"
	"io"
	"os"
	"strings"
	"sync"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// routeHeader is the metadata key for header routing.
const routeHeader = "x-route-key"

// Router is a proxy router that sends messages to the correct backend
// by header (uses "x-route-key" as the routing key) or by service if
// no header is provided.
type Router struct {
	mu       sync.RWMutex                // mutex for atomic updates
	headers  map[string]*grpc.ClientConn // x-route-key value
	services map[string]*grpc.ClientConn // "pkg.Service"
	log      zerolog.Logger              // logger object
}

// NewRouter creates a Router, optionally seeded with header routes
// (x-route-key value -> conn) and service routes ("pkg.Service" -> conn).
// Either map may be nil. The router does not take ownership of the conns;
// the caller is responsible for closing them.
func NewRouter(headers, services map[string]*grpc.ClientConn, opts ...RouterOption) *Router {
	r := &Router{
		headers:  map[string]*grpc.ClientConn{},
		services: map[string]*grpc.ClientConn{},
		log:      zerolog.New(os.Stdout).With().Timestamp().Logger(),
	}
	for _, opt := range opts {
		opt(r)
	}
	for header, c := range headers {
		r.AddHeaderRoute(header, c)
	}
	for service, c := range services {
		r.AddServiceRoute(service, c)
	}
	return r
}

// AddHeaderRoute adds a header-based routing rule (x-route-key value -> conn),
// overwriting any existing route with the same key. The conn need not use
// RawCodec; the router forces it per call.
func (r *Router) AddHeaderRoute(header string, c *grpc.ClientConn) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.headers[header] = c
	r.log.Debug().Str("header", header).Str("addr", c.Target()).Msg("adding header route")
}

// AddServiceRoute adds a service-based routing rule ("pkg.Service" -> conn),
// overwriting any existing route with the same service. The service may also
// be given as a type path ("pkg/Service"), which is sanitized to "pkg.Service".
// The conn need not use RawCodec; the router forces it per call.
func (r *Router) AddServiceRoute(service string, c *grpc.ClientConn) {
	r.mu.Lock()
	defer r.mu.Unlock()
	service = sanitizeService(service)
	r.services[service] = c
	r.log.Debug().Str("service", service).Str("addr", c.Target()).Msg("adding service route")
}

// Handle proxies a gRPC call to the backend resolved by header or service.
// Use it as a grpc.UnknownServiceHandler alongside grpc.ForceServerCodec(RawCodec{}).
func (r *Router) Handle(_ any, down grpc.ServerStream) error {
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

	// Treat every call as bidi streaming, forcing RawCodec in case the
	// conn was created with a different default codec
	desc := &grpc.StreamDesc{ServerStreams: true, ClientStreams: true}
	up, err := cc.NewStream(upCtx, desc, fullMethod, grpc.ForceCodec(RawCodec{}))
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

// sanitizeService converts a service type path ("pkg/Service") into a gRPC
// service name ("pkg.Service").
func sanitizeService(service string) string {
	return strings.ReplaceAll(service, "/", ".")
}

// resolve gets the gRPCClientConn for a gRPC call.
func (r *Router) resolve(ctx context.Context, fullMethod string) (*grpc.ClientConn, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	md, _ := metadata.FromIncomingContext(ctx)
	if v := md.Get(routeHeader); len(v) > 0 {
		if c, ok := r.headers[v[0]]; ok {
			r.log.Debug().Str("method", fullMethod).Str("addr", c.Target()).Msg("dispatching method")
			return c, nil
		}
	}
	// fullMethod looks like "/pkg.Service/Method"
	svc := strings.SplitN(strings.TrimPrefix(fullMethod, "/"), "/", 2)[0]
	if c, ok := r.services[svc]; ok {
		r.log.Debug().Str("method", fullMethod).Str("addr", c.Target()).Msg("dispatching method")
		return c, nil
	}
	// Reject if there is no recognized header key or service
	r.log.Error().Str("method", fullMethod).Msg("no route for method")
	return nil, status.Errorf(codes.Unimplemented, "no route for %s", fullMethod)
}
