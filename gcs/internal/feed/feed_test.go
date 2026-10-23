package feed

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	framepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/frame"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	"google.golang.org/protobuf/proto"
)

func TestVehicleOf(t *testing.T) {
	for producer, want := range map[string]string{
		"drone1.front":          "drone1",
		"drone1.gimbal/front":   "drone1",
		"drone1.telemetry":      "drone1",
		"site.drone1.telemetry": "site.drone1",
		"drone1":                "drone1",
	} {
		if got := VehicleOf(producer); got != want {
			t.Errorf("VehicleOf(%q) = %q, want %q", producer, got, want)
		}
	}
}

func TestDecode(t *testing.T) {
	frame, _ := proto.Marshal(framepb.EncodedFrame_builder{
		EncodedData: []byte{0, 0, 0, 1, 0x65}, Codec: framepb.Codec_CODEC_H264, Keyframe: true,
	}.Build())
	telemetry, _ := proto.Marshal(telemetrypb.Telemetry_builder{}.Build())

	msg, err := Decode("drone1.front", FrameType, frame)
	if err != nil {
		t.Fatal(err)
	}
	if msg.Vehicle != "drone1" || msg.Frame == nil || !msg.Frame.GetKeyframe() || msg.Telemetry != nil {
		t.Errorf("Decode(frame) = %+v, want a keyframe of drone1", msg)
	}
	// Without a payload type, the producer says what an input is
	if msg, err := Decode("drone1.front", "", frame); err != nil || msg.Frame == nil {
		t.Errorf("Decode(untyped frame) = %+v, %v, want a frame", msg, err)
	}
	if msg, err := Decode("drone1.telemetry", "", telemetry); err != nil || msg.Telemetry == nil {
		t.Errorf("Decode(untyped telemetry) = %+v, %v, want telemetry", msg, err)
	}
	if msg, err := Decode("drone1.telemetry", TelemetryType, telemetry); err != nil || msg.Telemetry == nil {
		t.Errorf("Decode(telemetry) = %+v, %v, want telemetry", msg, err)
	}

	if _, err := Decode("drone1.front", "steeleagle_protocol/v1/messages/frame/RawFrame", frame); err == nil {
		t.Error("Decode(RawFrame) succeeded, want an unsupported payload type")
	}
	if _, err := Decode("drone1.front", FrameType, []byte{0xff, 0xff}); err == nil {
		t.Error("Decode(garbage) succeeded, want an error")
	}
}

// TestDecodeCopies ensures that a decoded frame doesn't share the input's
// memory, which is reused once the input is dropped.
func TestDecodeCopies(t *testing.T) {
	data, _ := proto.Marshal(framepb.EncodedFrame_builder{EncodedData: []byte("frame")}.Build())
	msg, err := Decode("drone1.front", FrameType, data)
	if err != nil {
		t.Fatal(err)
	}
	clear(data)
	if got := string(msg.Frame.GetEncodedData()); got != "frame" {
		t.Errorf("encoded data = %q after the input was reused, want %q", got, "frame")
	}
}

// TestRun ensures that Run hands the engine's inputs to its handler, and
// returns nil once its context is done. Uriel names are shared by every
// process on the machine, so they are made unique to this one.
func TestRun(t *testing.T) {
	pid := os.Getpid()
	vehicle := fmt.Sprintf("gcs-vehicle-%d", pid)
	engine := fmt.Sprintf("gcs-%d", pid)
	producer := vehicle + ".telemetry"

	lcs := fmt.Sprintf("gcs-lcs-%d", pid)
	server, err := uriel.NewServer(lcs)
	if err != nil {
		t.Fatal(err)
	}
	defer server.Close()
	if err := server.AddEngine(engine); err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	msgs := make(chan Message, 16)
	done := make(chan error, 1)
	go func() { done <- Run(ctx, engine, 4096, zerolog.Nop(), func(m Message) { msgs <- m }) }()

	client, err := uriel.NewClient(vehicle, lcs)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	if err := client.AddProducer(producer); err != nil {
		t.Fatal(err)
	}
	spec := fmt.Sprintf(`
[[producers]]
name = %q

[[engines]]
name = %q
location = "local"

[[edges]]
from = %q
to = %q
timeout = "1s"
`, producer, engine, producer, engine)
	if err := client.AddFlow(vehicle, spec); err != nil {
		t.Fatal(err)
	}
	p, err := uriel.NewProducer(producer, TelemetryType, 4096)
	if err != nil {
		t.Fatal(err)
	}
	defer p.Close()

	data, _ := proto.Marshal(telemetrypb.Telemetry_builder{}.Build())
	// The engine may not be ready for the first inputs
	deadline := time.After(10 * time.Second)
	var msg Message
receive:
	for {
		if _, err := p.Send(vehicle, data); err != nil {
			t.Fatal(err)
		}
		select {
		case msg = <-msgs:
			break receive
		case err := <-done:
			t.Fatalf("Run() = %v before any input", err)
		case <-time.After(200 * time.Millisecond):
		case <-deadline:
			t.Fatal("no input reached the handler")
		}
	}
	if msg.Producer != producer || msg.Vehicle != vehicle || msg.Telemetry == nil {
		t.Errorf("got %+v, want telemetry of %s", msg, producer)
	}

	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Errorf("Run() = %v after its context was done, want nil", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Run did not return once its context was done")
	}
}
