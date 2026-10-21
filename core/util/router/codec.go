package router

import (
	"fmt"

	"google.golang.org/protobuf/proto"
)

type frame struct{ payload []byte }

// RawCodec is a gRPC codec that forwards frame bytes untouched and falls back
// to standard protobuf encoding for any other message. This lets a single server
// host registered services alongside Handle as an UnknownServiceHandler.
type RawCodec struct{}

func (RawCodec) Marshal(v any) ([]byte, error) {
	switch m := v.(type) {
	case *frame:
		return m.payload, nil
	case proto.Message:
		return proto.Marshal(m)
	}
	return nil, fmt.Errorf("RawCodec: unexpected type %T", v)
}

func (RawCodec) Unmarshal(data []byte, v any) error {
	switch m := v.(type) {
	case *frame:
		// Copy into a fresh buffer since gRPC may reuse data after Unmarshal returns,
		// and the previous payload may still be queued for writing by the transport
		m.payload = append([]byte(nil), data...)
		return nil
	case proto.Message:
		return proto.Unmarshal(data, m)
	}
	return fmt.Errorf("RawCodec: unexpected type %T", v)
}

// "proto" keeps the content-type as application/grpc+proto on both legs.
func (RawCodec) Name() string { return "proto" }
