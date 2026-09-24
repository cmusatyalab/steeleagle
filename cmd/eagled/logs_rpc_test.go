package main_test

import (
	"context"
	"errors"
	"io"
	"strings"
	"testing"
	"time"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func logSources(t *testing.T, inst *eagledInstance) map[string]*eagledpb.LogSource {
	t.Helper()
	resp, err := inst.Client.ListLogSources(t.Context(), eagledpb.ListLogSourcesRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("ListLogSources: %v", err)
	}
	out := map[string]*eagledpb.LogSource{}
	for _, s := range resp.GetSources() {
		out[s.GetName()] = s
	}
	return out
}

// waitForSource polls ListLogSources until pred(source) holds.
func waitForSource(t *testing.T, inst *eagledInstance, name string, pred func(*eagledpb.LogSource) bool) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if s, ok := logSources(t, inst)[name]; ok && pred(s) {
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("source %q never satisfied the condition; sources = %v", name, logSources(t, inst))
}

func TestListLogSourcesReportsRunningState(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()
	const name, driver = "harpy", "mockdriver"
	writeMockDriver(t, inst.DataDir, driver)
	if _, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: baseConfig(inst, freePort(t), name, driver),
	}.Build()); err != nil {
		t.Fatalf("Configure: %v", err)
	}

	running := func(s *eagledpb.LogSource) bool { return s.GetRunning() && s.GetSizeBytes() > 0 }
	waitForSource(t, inst, "daemon", running)
	waitForSource(t, inst, "harpy", running)
	waitForSource(t, inst, "harpy-driver", running)

	if _, err := inst.Client.StopVehicles(ctx, eagledpb.StopVehiclesRequest_builder{Names: []string{name}}.Build()); err != nil {
		t.Fatalf("StopVehicles: %v", err)
	}
	stopped := func(s *eagledpb.LogSource) bool { return !s.GetRunning() }
	waitForSource(t, inst, "harpy", stopped)
	waitForSource(t, inst, "harpy-driver", stopped)
	waitForSource(t, inst, "daemon", running) // the daemon itself is always running

	if _, err := inst.Client.ForgetVehicles(ctx, eagledpb.ForgetVehiclesRequest_builder{Names: []string{name}}.Build()); err != nil {
		t.Fatalf("ForgetVehicles: %v", err)
	}
	waitForSource(t, inst, "harpy", stopped) // still listed: logs outlive the vehicle
}

// drain reads a non-follow stream to EOF.
func drain(t *testing.T, ctx context.Context, inst *eagledInstance, req *eagledpb.StreamLogsRequest) []*eagledpb.LogRecord {
	t.Helper()
	stream, err := inst.Client.StreamLogs(ctx, req)
	if err != nil {
		t.Fatalf("StreamLogs: %v", err)
	}
	var out []*eagledpb.LogRecord
	for {
		rec, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			return out
		}
		if err != nil {
			t.Fatalf("Recv: %v", err)
		}
		out = append(out, rec)
	}
}

func TestStreamLogsBacklogAndResume(t *testing.T) {
	inst := startEagled(t, "")
	ctx, cancel := context.WithTimeout(t.Context(), 15*time.Second)
	defer cancel()
	writeMockDriver(t, inst.DataDir, "mockdriver")
	if _, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: baseConfig(inst, freePort(t), "harpy", "mockdriver"),
	}.Build()); err != nil {
		t.Fatalf("Configure: %v", err)
	}
	waitForSource(t, inst, "daemon", func(s *eagledpb.LogSource) bool { return s.GetSizeBytes() > 0 })

	first := drain(t, ctx, inst, eagledpb.StreamLogsRequest_builder{Sources: []string{"daemon"}, Tail: 1000}.Build())
	if len(first) == 0 {
		t.Fatal("expected daemon backlog")
	}
	var sawConfigure bool
	for i, r := range first {
		if r.GetSource() != "daemon" || r.GetTime() == nil || r.GetDropped() != 0 {
			t.Fatalf("record %d malformed: %v", i, r)
		}
		if i > 0 && r.GetSeq() <= first[i-1].GetSeq() {
			t.Fatalf("seq not increasing at %d", i)
		}
		if strings.Contains(r.GetText(), "Configure received") {
			sawConfigure = true
		}
	}
	if !sawConfigure {
		t.Fatal("backlog missing the Configure log line")
	}

	last := first[len(first)-1].GetSeq()
	resumed := drain(t, ctx, inst, eagledpb.StreamLogsRequest_builder{
		Sources:  []string{"daemon"},
		Tail:     1000, // must be ignored for a source that has a cursor
		AfterSeq: map[string]uint64{"daemon": last},
	}.Build())
	for i, r := range resumed {
		if r.GetSeq() != last+uint64(i)+1 {
			t.Fatalf("resumed record %d has seq %d, want %d (no repeats, no gaps)", i, r.GetSeq(), last+uint64(i)+1)
		}
	}
}

func TestStreamLogsFollowsLiveThenEndsUnavailableOnShutdown(t *testing.T) {
	inst := startEagled(t, "")
	ctx, cancel := context.WithTimeout(t.Context(), 20*time.Second)
	defer cancel()

	stream, err := inst.Client.StreamLogs(ctx, eagledpb.StreamLogsRequest_builder{
		Sources: []string{"daemon"}, Tail: 1, Follow: true,
	}.Build())
	if err != nil {
		t.Fatalf("StreamLogs: %v", err)
	}
	// The single backlog record proves the server has already subscribed
	// (it subscribes before reading the backlog), so nothing below can race.
	first, err := stream.Recv()
	if err != nil {
		t.Fatalf("first Recv: %v", err)
	}

	writeMockDriver(t, inst.DataDir, "mockdriver")
	if _, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: baseConfig(inst, freePort(t), "harpy", "mockdriver"),
	}.Build()); err != nil {
		t.Fatalf("Configure: %v", err)
	}
	for {
		rec, err := stream.Recv()
		if err != nil {
			t.Fatalf("Recv while waiting for live record: %v", err)
		}
		if rec.GetSeq() <= first.GetSeq() {
			t.Fatalf("live record seq %d not after backlog seq %d", rec.GetSeq(), first.GetSeq())
		}
		if strings.Contains(rec.GetText(), "Configure received") {
			break
		}
	}

	if _, err := inst.Client.RestartDaemon(ctx, eagledpb.RestartDaemonRequest_builder{}.Build()); err != nil {
		t.Fatalf("RestartDaemon: %v", err)
	}
	for {
		if _, err := stream.Recv(); err != nil {
			if code := status.Code(err); code != codes.Unavailable {
				t.Fatalf("stream ended with %v, want Unavailable", err)
			}
			return
		}
	}
}
