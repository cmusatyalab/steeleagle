package vehicle_test

import (
	"fmt"
	"os"
	"testing"

	gabriel "github.com/cmusatyalab/gabriel/go"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
)

// gabrielMaxFrameSize is the largest frame the test producer takes.
const gabrielMaxFrameSize = 1 << 20

// TestGabrielBindingLinks checks that Gabriel's Go binding is built and
// linked: that a server and a producer that names its input type start and
// stop. Gabriel's names are global to the machine, so they include the process
// id.
func TestGabrielBindingLinks(t *testing.T) {
	name := fmt.Sprintf("steeleagle-test-%d", os.Getpid())

	server, err := gabriel.NewServer(name + ".server")
	if err != nil {
		t.Fatalf("creating a Gabriel server: %v", err)
	}
	defer server.Close()

	frameType := string((*telemetrypb.EncodedFrame)(nil).ProtoReflect().Descriptor().FullName())
	producer, err := gabriel.NewProducer(name+".frames", frameType, gabrielMaxFrameSize)
	if err != nil {
		t.Fatalf("creating a Gabriel producer: %v", err)
	}
	if err := producer.Close(); err != nil {
		t.Fatalf("closing the Gabriel producer: %v", err)
	}
}
