package core

import (
    "strings"
    "context"
    "fmt"
    "encoding/json"
    
    "google.golang.org/grpc"
    "google.golang.org/grpc/metadata"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "github.com/mwitkow/grpc-proxy/proxy"
)

type VehicleResult struct {
    Name     string      `json:"name"`
    Code     codes.Code  `json:"code"`
    Message  string      `json:"message,omitempty"`
    err      error
}

func (i *Vehicle) getProxyDirector() proxy.StreamDirector {
    return func(ctx context.Context, method string) (context.Context, grpc.ClientConnInterface, error) {
        if strings.Contains(method, ".Control/") {
            return ctx, i.services.control, nil
        } else if strings.Contains(method, ".Mission/") {
            return ctx, i.services.mission, nil
        }
        
        return nil, nil, status.Errorf(codes.Unimplemented, "Unknown method")
    }
}

func (i *Backend) getProxyHandler() grpc.StreamHandler {
    return func(srv interface{}, ss grpc.ServerStream) error {
        fullMethod, _ := grpc.MethodFromServerStream(ss)

        md, ok := metadata.FromIncomingContext(ss.Context())
        if !ok {
            return status.Error(codes.InvalidArgument, "could not read metadata for request, target vehicle metadata is required")
        }

        vehicles := md["vehicles"]
        if len(vehicles) == 0 {
            return status.Error(codes.InvalidArgument, "no vehicles targeted by request, ignoring")
        }
        
        // Get the incoming message
        req := make([]byte, 0)
        if err := ss.RecvMsg(req); err != nil {
            return err
        }

        // Must lock vehicle set to prevent concurrent overwrites
        i.mu.RLock()

        // Fan out to all targeted vehicles concurrently
        results := make(chan VehicleResult, len(vehicles))
        for _, name := range(vehicles) {
            serviceName := fullMethod[:strings.LastIndex(fullMethod, "/")]
            v, ok := i.vehicles[name]
            if !ok {
                results <- VehicleResult{
                    Name: name,
                    Code: codes.InvalidArgument,
                    Message: fmt.Sprintf("vehicle %s does not exist", name),
                    err: status.Errorf(codes.InvalidArgument, "vehicle %s does not exist", name),
                }
                continue
            }
            conn, ok := v.services[serviceName]
            if !ok {
                results <- VehicleResult{
                    Name: name, 
                    Code: codes.InvalidArgument,
                    Message: fmt.Sprintf("vehicle %s does not have service %s registered", name, serviceName),
                    err: status.Errorf(codes.InvalidArgument, "vehicle %s does not have service %s registered", name, serviceName),
                }
                continue
            }

            go func(name string, cc *grpc.ClientConn) {
                ctx := ss.Context()
                clientStream, err := cc.NewStream(ctx, &grpc.StreamDesc{}, fullMethod)
                if err != nil {
                    status, _ := status.FromError(err)
                    results <- VehicleResult{Name: name, Code: status.Code(), Message: status.Message(), err: err}
                    return
                }

                // Forward the request frame
                if err := clientStream.SendMsg(req); err != nil {
                    status, _ := status.FromError(err)
                    results <- VehicleResult{Name: name, Code: status.Code(), Message: status.Message(), err: err}
                    return
                }
                clientStream.CloseSend()

                // Receive empty response
                resp := make([]byte, 0)
                if err := clientStream.RecvMsg(resp); err != nil {
                    status, _ := status.FromError(err)
                    results <- VehicleResult{Name: name, Code: status.Code(), Message: status.Message(), err: err}
                    return
                }
                results <- VehicleResult{Name: name, err: nil}
            }(name, conn)
        }

        // Only need to hold the lock when requests are dispatched
        i.mu.RUnlock()

        // Collect all results into this JSON map
        resultMap := make(map[string]VehicleResult, len(vehicles))
        
        // Flag to check if any calls failed
        anyFailed := false
        for range vehicles {
            r := <-results

            if r.err != nil {
                anyFailed = true
            }

            resultMap[r.Name] = r
        }

        // Send JSON back as binary; do this because metadata keys are automatically set
        // to lowercase by GRPC so we don't want name collision issues if vehicle names
        // are uppercase
        b, err := json.Marshal(resultMap)
        if err != nil {
            return status.Errorf(codes.Internal, "failed to marshal vehicle results: %v", err)
        }
        // As a client, you can get the results as follows by unmarshaling the trailer
        // metadata for "results-bin" and iterating through the keys
        ss.SetTrailer(metadata.Pairs("results-bin", string(b)))

        if anyFailed {
            return status.Error(codes.Internal, "one or more vehicles failed")
        }
        // If nothing failed, send an empty frame
        // NOTE: this will not work for an RPC that sends back a non-empty result,
        // so all proxied RPCs MUST send back empty results
        resp := make([]byte, 0)
        return ss.SendMsg(resp)
    }
}
