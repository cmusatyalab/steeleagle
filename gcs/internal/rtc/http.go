package rtc

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"time"
)

const (
	// maxOfferSize is the largest offer a browser may send.
	maxOfferSize = 1 << 20
	// gatherTimeout is how long an answer waits for its ICE candidates.
	gatherTimeout = 10 * time.Second
)

// ServeOffer answers an [Offer] that is POSTed as JSON with an [Answer].
func (h *Hub) ServeOffer(w http.ResponseWriter, r *http.Request) {
	var offer Offer
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxOfferSize)).Decode(&offer); err != nil {
		http.Error(w, "invalid offer: "+err.Error(), http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), gatherTimeout)
	defer cancel()
	answer, err := h.Connect(ctx, offer)
	switch {
	case errors.Is(err, ErrClosed):
		http.Error(w, err.Error(), http.StatusServiceUnavailable)
		return
	case err != nil:
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	writeJSON(w, answer)
}

// ServeStreams lists the producers the hub has received from as JSON
// [StreamInfo]s.
func (h *Hub) ServeStreams(w http.ResponseWriter, r *http.Request) {
	streams := h.Streams()
	if streams == nil {
		streams = []StreamInfo{}
	}
	writeJSON(w, streams)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
