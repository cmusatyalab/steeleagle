package daemon

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"testing"

	"github.com/adrg/xdg"
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TestTransferLaw ensures that the daemon law lets privileged and external
// callers transfer files and models while the daemon is online.
func TestTransferLaw(t *testing.T) {
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		t.Fatal(err)
	}
	p, err := policy.NewPolicy(law, policy.WithLogger(testLogger()))
	if err != nil {
		t.Fatal(err)
	}
	for _, code := range []string{"privileged", "external"} {
		for _, method := range []string{
			daemonpb.TransferService_TransferFile_FullMethodName,
			daemonpb.TransferService_TransferModel_FullMethodName,
		} {
			command := code + "/" + method[1:]
			if allowed, _, err := p.SafeCheckAndTransit(context.Background(), command); err != nil || !allowed {
				t.Errorf("expected %s allowed, got %v, %v", command, allowed, err)
			}
		}
	}
}

// transferChunk is a chunk of a transfer in a test.
type transferChunk struct {
	data          string
	number, total int32
	filename      string
}

// chunks splits data into numbered chunks of a transfer named filename.
func chunks(filename string, data ...string) []transferChunk {
	var c []transferChunk
	for i, d := range data {
		c = append(c, transferChunk{d, int32(i + 1), int32(len(data)), filename})
	}
	return c
}

// transfer sends the chunks with send, closes the stream, and returns the
// chunk numbers acknowledged by recv and the final error.
func transfer(chunks []transferChunk, send func(transferChunk) error, closeSend func() error,
	recv func() (int32, error)) ([]int32, error) {
	for _, c := range chunks {
		if err := send(c); err != nil {
			break // the stream ended, so its status comes from recv
		}
	}
	closeSend()
	var received []int32
	for {
		number, err := recv()
		if errors.Is(err, io.EOF) {
			return received, nil
		}
		if err != nil {
			return received, err
		}
		received = append(received, number)
	}
}

// TestTransfer ensures that files and models are saved in full to their
// directories under their file names, replacing older ones, with each chunk
// acknowledged, and that invalid transfers are rejected and leave nothing
// behind.
func TestTransfer(t *testing.T) {
	t.Setenv("XDG_DATA_HOME", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)
	_, addr := startRoutingDaemon(t, "[daemon]\n")
	client := daemonpb.NewTransferServiceClient(dial(t, addr))
	files, models := filepath.Join(xdg.DataHome, "steeleagle", "files"), filepath.Join(xdg.DataHome, "steeleagle", "models")

	transferFile := func(c []transferChunk) ([]int32, error) {
		stream, err := client.TransferFile(context.Background())
		if err != nil {
			return nil, err
		}
		return transfer(c, func(c transferChunk) error {
			return stream.Send(daemonpb.TransferFileRequest_builder{
				Chunk: []byte(c.data), Number: c.number, Total: c.total, Filename: c.filename,
			}.Build())
		}, stream.CloseSend, func() (int32, error) {
			resp, err := stream.Recv()
			return resp.GetReceived(), err
		})
	}
	transferModel := func(c []transferChunk) ([]int32, error) {
		stream, err := client.TransferModel(context.Background())
		if err != nil {
			return nil, err
		}
		return transfer(c, func(c transferChunk) error {
			return stream.Send(daemonpb.TransferModelRequest_builder{
				Chunk: []byte(c.data), Number: c.number, Total: c.total, Filename: c.filename,
			}.Build())
		}, stream.CloseSend, func() (int32, error) {
			resp, err := stream.Recv()
			return resp.GetReceived(), err
		})
	}
	expectSaved := func(path, want string) {
		t.Helper()
		if got, err := os.ReadFile(path); err != nil || string(got) != want {
			t.Errorf("expected %s to hold %q, got %q, %v", path, want, got, err)
		}
	}

	received, err := transferFile(chunks("mission.json", "a", "b", "c"))
	if err != nil || len(received) != 3 || received[0] != 1 || received[2] != 3 {
		t.Errorf("expected all 3 chunks acknowledged, got %v, %v", received, err)
	}
	expectSaved(filepath.Join(files, "mission.json"), "abc")
	if _, err := transferModel(chunks("yolo.pt", "weights")); err != nil {
		t.Errorf("model transfer failed: %v", err)
	}
	expectSaved(filepath.Join(models, "yolo.pt"), "weights")
	if _, err := transferFile(chunks("mission.json", "new")); err != nil {
		t.Errorf("replacing transfer failed: %v", err)
	}
	expectSaved(filepath.Join(files, "mission.json"), "new")

	for name, c := range map[string][]transferChunk{
		"no name":         chunks("", "a"),
		"directory":       chunks("../config.toml", "a"),
		"subdirectory":    chunks("a/b", "a"),
		"backslash":       chunks(`a\b`, "a"),
		"dot dot":         chunks("..", "a"),
		"no chunks":       nil,
		"no total":        {{"a", 1, 0, "bad"}},
		"skipped chunk":   {{"a", 1, 3, "bad"}, {"c", 3, 3, "bad"}},
		"first chunk 0":   {{"a", 0, 1, "bad"}},
		"changed total":   {{"a", 1, 2, "bad"}, {"b", 2, 3, "bad"}},
		"ended too early": {{"a", 1, 2, "bad"}},
	} {
		if _, err := transferFile(c); status.Code(err) != codes.InvalidArgument {
			t.Errorf("%s: expected InvalidArgument, got %v", name, err)
		}
	}
	for _, dir := range []string{files, models} {
		entries, err := os.ReadDir(dir)
		if err != nil {
			t.Fatal(err)
		}
		for _, e := range entries {
			if e.Name() != "mission.json" && e.Name() != "yolo.pt" {
				t.Errorf("expected no file left by a failed transfer, got %s", filepath.Join(dir, e.Name()))
			}
		}
	}
	if _, err := os.Stat(filepath.Join(xdg.DataHome, "steeleagle", "config.toml")); err == nil {
		t.Error("expected no transfer saved outside the files directory")
	}
}
