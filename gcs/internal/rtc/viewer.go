package rtc

import (
	"context"
	"errors"
	"fmt"
	"io"
	"sync"

	"github.com/pion/webrtc/v4"
	"github.com/pion/webrtc/v4/pkg/media"
	"github.com/rs/zerolog"
)

// maxVideos is the most cameras a peer connection may receive.
const maxVideos = 16

// ErrClosed is returned by [Hub.Connect] once the hub is closed.
var ErrClosed = errors.New("hub is closed")

// Offer is a browser's request to connect.
type Offer struct {
	// SDP is the browser's offer, with its ICE candidates gathered. It has a
	// receive-only video transceiver for each camera in Video, and may have a
	// data channel.
	SDP string `json:"sdp"`
	// Video are the producers whose video the browser receives, e.g.
	// "drone1.front", in the order of its video transceivers. Each track's
	// stream ID is its producer.
	Video []string `json:"video"`
}

// Answer is the GCS's answer to an [Offer].
type Answer struct {
	Type string `json:"type"`
	SDP  string `json:"sdp"`
}

// viewer is a browser's peer connection.
type viewer struct {
	hub   *Hub
	pc    *webrtc.PeerConnection
	sinks map[string]*sink // by producer
	log   zerolog.Logger
	// data is the viewer's open data channel, if any; guarded by the hub's
	// mu
	data *webrtc.DataChannel

	mu      sync.Mutex
	started bool
	closed  bool
}

// Connect answers a browser's offer, adding a viewer that receives the video
// of the cameras it asks for once it connects, and every vehicle's telemetry
// and frame metadata on the data channel it opens. Connect waits for the
// GCS's ICE candidates, which the answer includes, until ctx is done.
func (h *Hub) Connect(ctx context.Context, offer Offer) (Answer, error) {
	if len(offer.Video) > maxVideos {
		return Answer{}, fmt.Errorf("asked for %d videos, at most %d are allowed", len(offer.Video), maxVideos)
	}
	sinks := map[string]*sink{}
	for _, producer := range offer.Video {
		if producer == "" {
			return Answer{}, errors.New("asked for a video without a producer")
		}
		if _, ok := sinks[producer]; ok {
			return Answer{}, fmt.Errorf("asked for the video of %q twice", producer)
		}
		sinks[producer] = nil
	}

	pc, err := h.api.NewPeerConnection(webrtc.Configuration{ICEServers: h.iceServers})
	if err != nil {
		return Answer{}, fmt.Errorf("could not create peer connection: %w", err)
	}
	v := &viewer{hub: h, pc: pc, sinks: sinks, log: h.log.With().Strs("video", offer.Video).Logger()}
	h.mu.Lock()
	if h.closed {
		h.mu.Unlock()
		pc.Close()
		return Answer{}, ErrClosed
	}
	h.viewers[v] = struct{}{}
	h.mu.Unlock()

	answer, err := v.answer(ctx, offer)
	if err != nil {
		v.close()
		return Answer{}, err
	}
	v.log.Info().Msg("viewer connecting")
	return answer, nil
}

// answer negotiates the viewer's peer connection.
func (v *viewer) answer(ctx context.Context, offer Offer) (Answer, error) {
	pc := v.pc
	pc.OnConnectionStateChange(func(state webrtc.PeerConnectionState) {
		v.log.Debug().Stringer("state", state).Msg("viewer connection changed")
		switch state {
		case webrtc.PeerConnectionStateConnected:
			v.start()
		case webrtc.PeerConnectionStateFailed, webrtc.PeerConnectionStateClosed:
			v.close()
		}
	})
	pc.OnDataChannel(func(dc *webrtc.DataChannel) {
		dc.OnOpen(func() { v.openData(dc) })
		dc.OnClose(func() { v.closeData(dc) })
	})

	if err := pc.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeOffer, SDP: offer.SDP}); err != nil {
		return Answer{}, fmt.Errorf("invalid offer: %w", err)
	}
	transceivers := 0
	for _, t := range pc.GetTransceivers() {
		if t.Kind() == webrtc.RTPCodecTypeVideo {
			transceivers++
		}
	}
	if transceivers < len(offer.Video) {
		return Answer{}, fmt.Errorf("offer has %d video transceivers for %d videos", transceivers, len(offer.Video))
	}
	// Tracks take the offer's video transceivers in order
	for _, producer := range offer.Video {
		track, err := webrtc.NewTrackLocalStaticSample(H264Codec, producer, producer)
		if err != nil {
			return Answer{}, fmt.Errorf("could not create track: %w", err)
		}
		sender, err := pc.AddTrack(track)
		if err != nil {
			return Answer{}, fmt.Errorf("could not add track: %w", err)
		}
		// RTCP must be read for the sender to work. A browser's requests for
		// keyframes can't reach the encoder, which sends them regularly
		go func() {
			buf := make([]byte, 1500)
			for {
				if _, _, err := sender.Read(buf); err != nil {
					return
				}
			}
		}()
		v.sinks[producer] = &sink{track: track, queue: make(chan media.Sample, sinkQueue)}
	}

	answer, err := pc.CreateAnswer(nil)
	if err != nil {
		return Answer{}, fmt.Errorf("could not answer offer: %w", err)
	}
	gathered := webrtc.GatheringCompletePromise(pc)
	if err := pc.SetLocalDescription(answer); err != nil {
		return Answer{}, fmt.Errorf("could not answer offer: %w", err)
	}
	select {
	case <-gathered:
	case <-ctx.Done():
		return Answer{}, fmt.Errorf("could not gather ICE candidates: %w", ctx.Err())
	}
	local := pc.LocalDescription()
	return Answer{Type: local.Type.String(), SDP: local.SDP}, nil
}

// start starts sending the viewer's videos, once it connects.
func (v *viewer) start() {
	v.mu.Lock()
	defer v.mu.Unlock()
	if v.started || v.closed {
		return
	}
	v.started = true
	v.log.Info().Msg("viewer connected")
	for producer, s := range v.sinks {
		go v.write(producer, s)
		v.hub.attach(producer, s)
	}
}

// write writes the frames queued for s to its track, until its queue closes.
func (v *viewer) write(producer string, s *sink) {
	for sample := range s.queue {
		if err := s.track.WriteSample(sample); err != nil && !errors.Is(err, io.ErrClosedPipe) {
			v.log.Debug().Err(err).Str("producer", producer).Msg("could not send frame")
		}
	}
}

// openData starts sending telemetry and frame metadata on dc, first the last
// telemetry of every vehicle.
func (v *viewer) openData(dc *webrtc.DataChannel) {
	h := v.hub
	h.mu.Lock()
	if _, ok := h.viewers[v]; !ok {
		h.mu.Unlock()
		return
	}
	v.data = dc
	messages := make([][]byte, 0, len(h.telemetry))
	for _, t := range h.telemetry {
		messages = append(messages, t.message)
	}
	h.mu.Unlock()
	for _, message := range messages {
		send([]*webrtc.DataChannel{dc}, message)
	}
}

// closeData stops sending on dc.
func (v *viewer) closeData(dc *webrtc.DataChannel) {
	v.hub.mu.Lock()
	defer v.hub.mu.Unlock()
	if v.data == dc {
		v.data = nil
	}
}

// close removes the viewer from the hub, and closes its peer connection.
func (v *viewer) close() {
	v.mu.Lock()
	if v.closed {
		v.mu.Unlock()
		return
	}
	v.closed = true
	started := v.started
	v.mu.Unlock()

	h := v.hub
	h.mu.Lock()
	delete(h.viewers, v)
	h.mu.Unlock()
	for producer, s := range v.sinks {
		if s == nil {
			continue
		}
		h.detach(producer, s)
		// Nothing queues frames once the sink is detached
		if started {
			close(s.queue)
		}
	}
	if err := v.pc.Close(); err != nil {
		v.log.Debug().Err(err).Msg("could not close peer connection")
	}
	v.log.Info().Msg("viewer disconnected")
}
