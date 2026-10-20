package router

import "fmt"

type frame struct{ payload []byte }

// Implementation of a gRPC server codec.
type rawCodec struct{}

func (rawCodec) Marshal(v any) ([]byte, error) {
	f, ok := v.(*frame)
	if !ok {
		return nil, fmt.Errorf("rawCodec: unexpected type %T", v)
	}
	return f.payload, nil
}

func (rawCodec) Unmarshal(data []byte, v any) error {
	f, ok := v.(*frame)
	if !ok {
		return fmt.Errorf("rawCodec: unexpected type %T", v)
	}
	// Copy into a fresh buffer since gRPC may reuse data after Unmarshal returns,
	// and the previous payload may still be queued for writing by the transport
	f.payload = append([]byte(nil), data...)
	return nil
}

// "proto" keeps the content-type as application/grpc+proto on both legs.
func (rawCodec) Name() string { return "proto" }
