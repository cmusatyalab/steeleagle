package rtc

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	framepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/frame"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/cmusatyalab/steeleagle/gcs/internal/feed"
	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
	"github.com/pion/webrtc/v4/pkg/media"
	"github.com/rs/zerolog"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Annex B access units: a keyframe is an IDR slice after its SPS and PPS, and
// a P-frame is a non-IDR slice.
var (
	keyframeData = []byte{0, 0, 0, 1, 0x67, 0x42, 0xe0, 0x1f, 0, 0, 0, 1, 0x68, 0xce, 0x3c, 0x80, 0, 0, 0, 1, 0x65, 0x88, 0x84}
	pframeData   = []byte{0, 0, 0, 1, 0x41, 0x9a, 0x02}
)

func newTestHub(t *testing.T) *Hub {
	t.Helper()
	hub, err := NewHub(Options{}, zerolog.Nop())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { hub.Close() })
	return hub
}

// frameMsg returns an H.264 frame of producer captured at.
func frameMsg(producer string, keyframe bool, at time.Time) feed.Message {
	data := pframeData
	if keyframe {
		data = keyframeData
	}
	return feed.Message{Producer: producer, Vehicle: feed.VehicleOf(producer), Frame: framepb.EncodedFrame_builder{
		Timestamp: timestamppb.New(at), EncodedData: data, Codec: framepb.Codec_CODEC_H264, Keyframe: keyframe,
	}.Build()}
}

// testSink returns a sink of the video of producer with a queue of n frames,
// attached to hub.
func testSink(hub *Hub, producer string, n int) *sink {
	s := &sink{queue: make(chan media.Sample, n)}
	hub.attach(producer, s)
	return s
}

// queued drains the frames queued for s.
func queued(s *sink) [][]byte {
	var frames [][]byte
	for {
		select {
		case sample := <-s.queue:
			frames = append(frames, sample.Data)
		default:
			return frames
		}
	}
}

// TestSinkStartsAtKeyframe ensures that a viewer of a camera that has sent
// no keyframe yet waits for one.
func TestSinkStartsAtKeyframe(t *testing.T) {
	hub := newTestHub(t)
	s := testSink(hub, "drone1.front", 8)
	now := time.Now()
	hub.Publish(frameMsg("drone1.front", false, now))
	if got := queued(s); len(got) != 0 {
		t.Fatalf("queued %d frames before a keyframe, want none", len(got))
	}
	hub.Publish(frameMsg("drone1.front", true, now.Add(time.Second)))
	hub.Publish(frameMsg("drone1.front", false, now.Add(2*time.Second)))
	if got := queued(s); len(got) != 2 || !bytes.Equal(got[0], keyframeData) {
		t.Errorf("queued %d frames, want the keyframe and the P-frame after it", len(got))
	}
}

// TestSinkReplaysGop ensures that a new viewer is sent the frames since the
// last keyframe, at once.
func TestSinkReplaysGop(t *testing.T) {
	hub := newTestHub(t)
	now := time.Now()
	hub.Publish(frameMsg("drone1.front", false, now))
	hub.Publish(frameMsg("drone1.front", true, now.Add(time.Second)))
	hub.Publish(frameMsg("drone1.front", false, now.Add(2*time.Second)))

	s := testSink(hub, "drone1.front", 8)
	var samples []media.Sample
	for len(s.queue) > 0 {
		samples = append(samples, <-s.queue)
	}
	if len(samples) != 2 || !bytes.Equal(samples[0].Data, keyframeData) || !bytes.Equal(samples[1].Data, pframeData) {
		t.Fatalf("replayed %d frames, want the keyframe and the P-frame after it", len(samples))
	}
	for _, sample := range samples {
		if sample.Duration != replayFrameDuration {
			t.Errorf("replayed a frame lasting %v, want %v", sample.Duration, replayFrameDuration)
		}
	}
}

// TestSinkSkipsToKeyframe ensures that a viewer whose queue fills skips to
// the next keyframe rather than decoding a broken stream.
func TestSinkSkipsToKeyframe(t *testing.T) {
	hub := newTestHub(t)
	s := testSink(hub, "drone1.front", 2)
	now := time.Now()
	for i := range 4 { // the third and fourth frames don't fit
		hub.Publish(frameMsg("drone1.front", i == 0, now.Add(time.Duration(i)*time.Second)))
	}
	if got := queued(s); len(got) != 2 {
		t.Fatalf("queued %d frames, want the 2 that fit", len(got))
	}
	hub.Publish(frameMsg("drone1.front", false, now.Add(5*time.Second)))
	if got := queued(s); len(got) != 0 {
		t.Fatalf("queued %d frames after losing one, want none until a keyframe", len(got))
	}
	hub.Publish(frameMsg("drone1.front", true, now.Add(6*time.Second)))
	if got := queued(s); len(got) != 1 || !bytes.Equal(got[0], keyframeData) {
		t.Errorf("queued %d frames, want the keyframe", len(got))
	}
}

// TestFrameDuration ensures that a frame lasts until the camera's next
// frame, bounded so a long gap doesn't stall the video.
func TestFrameDuration(t *testing.T) {
	hub := newTestHub(t)
	s := testSink(hub, "drone1.front", 8)
	now := time.Now()
	hub.Publish(frameMsg("drone1.front", true, now))
	hub.Publish(frameMsg("drone1.front", false, now.Add(50*time.Millisecond)))
	hub.Publish(frameMsg("drone1.front", false, now.Add(time.Minute)))
	var durations []time.Duration
	for len(s.queue) > 0 {
		durations = append(durations, (<-s.queue).Duration)
	}
	want := []time.Duration{defaultFrameDuration, 50 * time.Millisecond, maxFrameDuration}
	if len(durations) != len(want) {
		t.Fatalf("got %d frames, want %d", len(durations), len(want))
	}
	for i := range want {
		if durations[i] != want[i] {
			t.Errorf("frame %d lasts %v, want %v", i, durations[i], want[i])
		}
	}
}

// TestOtherCodecsNotStreamed ensures that frames that aren't H.264 never
// reach a track.
func TestOtherCodecsNotStreamed(t *testing.T) {
	hub := newTestHub(t)
	s := testSink(hub, "drone1.front", 8)
	for _, codec := range []framepb.Codec{framepb.Codec_CODEC_JPEG, framepb.Codec_CODEC_UNSPECIFIED} {
		hub.Publish(feed.Message{Producer: "drone1.front", Vehicle: "drone1", Frame: framepb.EncodedFrame_builder{
			EncodedData: []byte{0xff, 0xd8}, Codec: codec, Keyframe: true,
		}.Build()})
	}
	if got := queued(s); len(got) != 0 {
		t.Errorf("queued %d frames that aren't H.264, want none", len(got))
	}
}

func TestStreams(t *testing.T) {
	hub := newTestHub(t)
	hub.Publish(frameMsg("drone1.front", true, time.Now()))
	hub.Publish(feed.Message{Producer: "drone1.telemetry", Vehicle: "drone1", Telemetry: telemetrypb.Telemetry_builder{}.Build()})
	testSink(hub, "drone2.front", 1) // asked for, but never received

	streams := hub.Streams()
	if len(streams) != 2 {
		t.Fatalf("got %d streams, want 2: %+v", len(streams), streams)
	}
	if s := streams[0]; s.Producer != "drone1.front" || s.Vehicle != "drone1" || s.Kind != "video" {
		t.Errorf("got stream %+v, want the video of drone1.front", s)
	}
	if s := streams[1]; s.Producer != "drone1.telemetry" || s.Kind != "telemetry" {
		t.Errorf("got stream %+v, want the telemetry of drone1", s)
	}
}

// browser is a peer connection standing in for a browser's.
type browser struct {
	pc     *webrtc.PeerConnection
	tracks chan *webrtc.TrackRemote
	data   chan DataMessage
}

// connect connects a browser receiving the video of producers to the hub
// served by server.
func connect(t *testing.T, server *httptest.Server, producers ...string) *browser {
	t.Helper()
	b, offer := newBrowser(t, len(producers))
	answer, status := postOffer(t, server, Offer{SDP: offer, Video: producers})
	if status != http.StatusOK {
		t.Fatalf("offer answered with status %d", status)
	}
	if err := b.pc.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeAnswer, SDP: answer.SDP}); err != nil {
		t.Fatal(err)
	}
	return b
}

// newBrowser returns a browser with n video transceivers and a data channel,
// and its offer.
func newBrowser(t *testing.T, n int) (*browser, string) {
	t.Helper()
	pc, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { pc.Close() })
	b := &browser{pc: pc, tracks: make(chan *webrtc.TrackRemote, n), data: make(chan DataMessage, 64)}
	for range n {
		if _, err := pc.AddTransceiverFromKind(webrtc.RTPCodecTypeVideo,
			webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly}); err != nil {
			t.Fatal(err)
		}
	}
	pc.OnTrack(func(track *webrtc.TrackRemote, _ *webrtc.RTPReceiver) { b.tracks <- track })
	dc, err := pc.CreateDataChannel("data", nil)
	if err != nil {
		t.Fatal(err)
	}
	dc.OnMessage(func(msg webrtc.DataChannelMessage) {
		var m DataMessage
		if err := json.Unmarshal(msg.Data, &m); err == nil {
			b.data <- m
		}
	})
	offer, err := pc.CreateOffer(nil)
	if err != nil {
		t.Fatal(err)
	}
	gathered := webrtc.GatheringCompletePromise(pc)
	if err := pc.SetLocalDescription(offer); err != nil {
		t.Fatal(err)
	}
	<-gathered
	return b, pc.LocalDescription().SDP
}

func postOffer(t *testing.T, server *httptest.Server, offer Offer) (Answer, int) {
	t.Helper()
	body, _ := json.Marshal(offer)
	resp, err := http.Post(server.URL, "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var answer Answer
	if resp.StatusCode == http.StatusOK {
		if err := json.NewDecoder(resp.Body).Decode(&answer); err != nil {
			t.Fatal(err)
		}
	}
	return answer, resp.StatusCode
}

func serveOffers(t *testing.T, hub *Hub) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(hub.ServeOffer))
	t.Cleanup(server.Close)
	return server
}

// TestViewerReceives ensures that a browser receives the video it asks for,
// as a track whose stream is its producer, and every vehicle's telemetry and
// frame metadata on its data channel, first the telemetry sent before it
// connected.
func TestViewerReceives(t *testing.T) {
	hub := newTestHub(t)
	server := serveOffers(t, hub)
	hub.Publish(feed.Message{Producer: "drone1.telemetry", Vehicle: "drone1", Telemetry: telemetrypb.Telemetry_builder{}.Build()})
	now := time.Now()
	hub.Publish(frameMsg("drone1.front", true, now))

	b := connect(t, server, "drone1.front")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	var track *webrtc.TrackRemote
	select {
	case track = <-b.tracks:
	case <-ctx.Done():
		t.Fatal("no track received")
	}
	if track.StreamID() != "drone1.front" {
		t.Errorf("track's stream is %q, want its producer", track.StreamID())
	}
	if !strings.EqualFold(track.Codec().MimeType, webrtc.MimeTypeH264) {
		t.Errorf("track's codec is %q, want H.264", track.Codec().MimeType)
	}
	// The replayed keyframe arrives without another frame published
	track.SetReadDeadline(time.Now().Add(5 * time.Second))
	var packet rtp.Packet
	buf := make([]byte, 1500)
	n, _, err := track.Read(buf)
	if err != nil {
		t.Fatalf("no frame received: %v", err)
	}
	if err := packet.Unmarshal(buf[:n]); err != nil || len(packet.Payload) == 0 {
		t.Errorf("received an invalid packet: %v", err)
	}

	select {
	case m := <-b.data:
		if m.Type != "telemetry" || m.Producer != "drone1.telemetry" || m.Vehicle != "drone1" {
			t.Errorf("first data message is %+v, want drone1's last telemetry", m)
		}
	case <-ctx.Done():
		t.Fatal("no telemetry received")
	}
	// Frames published from now on are described on the data channel
	for {
		hub.Publish(frameMsg("drone1.front", false, time.Now()))
		select {
		case m := <-b.data:
			if m.Type != "frame" {
				continue
			}
			var frame map[string]any
			if err := json.Unmarshal(m.Frame, &frame); err != nil {
				t.Fatal(err)
			}
			if m.Producer != "drone1.front" || frame["codec"] != "CODEC_H264" {
				t.Errorf("frame metadata is %+v %v, want an H.264 frame of drone1.front", m, frame)
			}
			if _, ok := frame["encodedData"]; ok {
				t.Error("frame metadata has the encoded data")
			}
			return
		case <-time.After(100 * time.Millisecond):
		case <-ctx.Done():
			t.Fatal("no frame metadata received")
		}
	}
}

// TestViewerRemovedOnClose ensures that a viewer whose browser goes away
// stops being sent frames.
func TestViewerRemovedOnClose(t *testing.T) {
	hub := newTestHub(t)
	server := serveOffers(t, hub)
	b := connect(t, server, "drone1.front")
	waitFor(t, func() bool { return viewers(hub, "drone1.front") == 1 })
	b.pc.Close()
	waitFor(t, func() bool { return viewers(hub, "drone1.front") == 0 })
}

func viewers(hub *Hub, producer string) int {
	hub.mu.Lock()
	defer hub.mu.Unlock()
	if v, ok := hub.videos[producer]; ok {
		return len(v.sinks)
	}
	return 0
}

func waitFor(t *testing.T, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(40 * time.Second)
	for !cond() {
		if time.Now().After(deadline) {
			t.Fatal("timed out")
		}
		time.Sleep(20 * time.Millisecond)
	}
}

func TestConnectInvalid(t *testing.T) {
	hub := newTestHub(t)
	server := serveOffers(t, hub)
	_, oneVideo := newBrowser(t, 1)
	many := make([]string, maxVideos+1)
	for i := range many {
		many[i] = string(rune('a' + i))
	}
	for name, offer := range map[string]Offer{
		"too many videos":      {SDP: oneVideo, Video: many},
		"duplicate video":      {SDP: oneVideo, Video: []string{"drone1.front", "drone1.front"}},
		"unnamed video":        {SDP: oneVideo, Video: []string{""}},
		"too few transceivers": {SDP: oneVideo, Video: []string{"drone1.front", "drone1.rear"}},
		"invalid sdp":          {SDP: "v=0", Video: nil},
	} {
		if _, status := postOffer(t, server, offer); status != http.StatusBadRequest {
			t.Errorf("%s: got status %d, want %d", name, status, http.StatusBadRequest)
		}
	}
	hub.mu.Lock()
	defer hub.mu.Unlock()
	if len(hub.viewers) != 0 {
		t.Errorf("hub has %d viewers after invalid offers, want none", len(hub.viewers))
	}
}

func TestConnectClosed(t *testing.T) {
	hub := newTestHub(t)
	server := serveOffers(t, hub)
	_, offer := newBrowser(t, 0)
	hub.Close()
	if _, err := hub.Connect(context.Background(), Offer{SDP: offer}); !errors.Is(err, ErrClosed) {
		t.Errorf("Connect() = %v on a closed hub, want ErrClosed", err)
	}
	if _, status := postOffer(t, server, Offer{SDP: offer}); status != http.StatusServiceUnavailable {
		t.Errorf("got status %d on a closed hub, want %d", status, http.StatusServiceUnavailable)
	}
}
