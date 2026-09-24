package main

import (
	"context"
	"errors"
	"strings"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"github.com/cmusatyalab/steeleagle/cmd/eagled/logstore"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// StreamLogs sends the requested log backlog and, with follow set, live
// records until the client cancels. A daemon shutdown ends the stream with
// UNAVAILABLE so the caller knows to reconnect with its cursors.
func (d *daemon) StreamLogs(req *eagledpb.StreamLogsRequest, stream grpc.ServerStreamingServer[eagledpb.LogRecord]) error {
	ctx, cancel := context.WithCancel(stream.Context())
	defer cancel()
	go func() {
		select {
		case <-d.ctx.Done():
			cancel() // shutdown must not wait on long-lived streams
		case <-ctx.Done():
		}
	}()

	err := d.logs.Stream(ctx, logstore.StreamOptions{
		Sources:  req.GetSources(),
		Tail:     int(req.GetTail()),
		Follow:   req.GetFollow(),
		AfterSeq: req.GetAfterSeq(),
	}, func(rec logstore.Record) error {
		return stream.Send(eagledpb.LogRecord_builder{
			Source:  rec.Source,
			Seq:     rec.Seq,
			Time:    timestamppb.New(rec.Time),
			Level:   rec.Level,
			Text:    rec.Text,
			Dropped: rec.Dropped,
		}.Build())
	})
	switch {
	case err == nil:
		return nil
	case d.ctx.Err() != nil:
		return status.Error(codes.Unavailable, "eagled is shutting down")
	case errors.Is(err, context.Canceled):
		return nil // the client went away
	default:
		return err
	}
}

// ListLogSources reports every log source on disk and whether a live process
// is currently producing it.
func (d *daemon) ListLogSources(ctx context.Context, req *eagledpb.ListLogSourcesRequest) (*eagledpb.ListLogSourcesResponse, error) {
	running, aviary := d.runningLogProducers()
	var out []*eagledpb.LogSource
	for _, si := range d.logs.Sources() {
		out = append(out, eagledpb.LogSource_builder{
			Name:      si.Name,
			Running:   sourceRunning(si.Name, running, aviary),
			SizeBytes: si.SizeBytes,
		}.Build())
	}
	return eagledpb.ListLogSourcesResponse_builder{Sources: out}.Build(), nil
}

// runningLogProducers returns the names of currently running vehicles and
// whether any of them is simulated (so the shared aviary process is live).
// It deliberately avoids aviaryMu, which is held through slow aviary spawns.
func (d *daemon) runningLogProducers() (vehicles []string, aviary bool) {
	d.mu.Lock()
	defer d.mu.Unlock()
	for name, rv := range d.running {
		if !rv.running() {
			continue
		}
		vehicles = append(vehicles, name)
		if d.vehicleCfgs[name].Simulate {
			aviary = true
		}
	}
	return vehicles, aviary
}

// sourceRunning maps a log source to a live producer. Vehicle-scoped sources
// are named "<vehicle>" or "<vehicle>-<plugin>".
func sourceRunning(source string, runningVehicles []string, aviary bool) bool {
	switch source {
	case "daemon":
		return true
	case "aviary":
		return aviary
	}
	for _, name := range runningVehicles {
		if source == name || strings.HasPrefix(source, name+"-") {
			return true
		}
	}
	return false
}
