package download

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"testing"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// testChunk is a chunk of a transfer in a test.
type testChunk struct {
	data          string
	number, total int32
	filename      string
}

func (c *testChunk) GetChunk() []byte    { return []byte(c.data) }
func (c *testChunk) GetNumber() int32    { return c.number }
func (c *testChunk) GetTotal() int32     { return c.total }
func (c *testChunk) GetFilename() string { return c.filename }

// testAck is the acknowledgement of a chunk in a test.
type testAck struct {
	received int32
}

// fakeStream is a transfer stream that receives chunks and records the chunk
// numbers acknowledged, failing sends with sendErr if it is set.
type fakeStream struct {
	grpc.ServerStream
	chunks   []testChunk
	received []int32
	sendErr  error
}

func (s *fakeStream) Recv() (*testChunk, error) {
	if len(s.chunks) == 0 {
		return nil, io.EOF
	}
	c := s.chunks[0]
	s.chunks = s.chunks[1:]
	return &c, nil
}

func (s *fakeStream) Send(ack *testAck) error {
	if s.sendErr != nil {
		return s.sendErr
	}
	s.received = append(s.received, ack.received)
	return nil
}

// chunks splits data into numbered chunks of a transfer named filename.
func chunks(filename string, data ...string) []testChunk {
	var c []testChunk
	for i, d := range data {
		c = append(c, testChunk{d, int32(i + 1), int32(len(data)), filename})
	}
	return c
}

// download transfers the chunks to dir, returning the chunk numbers
// acknowledged and the error.
func download(dir string, s *fakeStream) ([]int32, error) {
	err := DownloadFile(zerolog.Nop(), s, dir, func(number int32) *testAck {
		return &testAck{number}
	})
	return s.received, err
}

// expectOnly fails the test if dir holds anything other than names.
func expectOnly(t *testing.T, dir string, names ...string) {
	t.Helper()
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]bool{}
	for _, n := range names {
		want[n] = true
	}
	for _, e := range entries {
		if !want[e.Name()] {
			t.Errorf("expected no file left by a failed transfer, got %s", filepath.Join(dir, e.Name()))
		}
	}
}

// TestDownloadFile ensures that a transfer is saved in full to dir under its
// file name, replacing an older one, with each chunk acknowledged.
func TestDownloadFile(t *testing.T) {
	dir := t.TempDir()
	expectSaved := func(want string) {
		t.Helper()
		path := filepath.Join(dir, "mission.json")
		if got, err := os.ReadFile(path); err != nil || string(got) != want {
			t.Errorf("expected %s to hold %q, got %q, %v", path, want, got, err)
		}
	}

	received, err := download(dir, &fakeStream{chunks: chunks("mission.json", "a", "b", "c")})
	if err != nil || len(received) != 3 || received[0] != 1 || received[1] != 2 || received[2] != 3 {
		t.Errorf("expected all 3 chunks acknowledged, got %v, %v", received, err)
	}
	expectSaved("abc")
	if _, err := download(dir, &fakeStream{chunks: chunks("mission.json", "new")}); err != nil {
		t.Errorf("replacing transfer failed: %v", err)
	}
	expectSaved("new")
	if _, err := download(dir, &fakeStream{chunks: chunks("empty", "")}); err != nil {
		t.Errorf("empty transfer failed: %v", err)
	}
	expectOnly(t, dir, "mission.json", "empty")
}

// TestDownloadFileInvalid ensures that invalid transfers are rejected and
// leave nothing behind.
func TestDownloadFileInvalid(t *testing.T) {
	dir := t.TempDir()
	for name, c := range map[string][]testChunk{
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
		if _, err := download(dir, &fakeStream{chunks: c}); status.Code(err) != codes.InvalidArgument {
			t.Errorf("%s: expected InvalidArgument, got %v", name, err)
		}
	}
	expectOnly(t, dir)
	if _, err := os.Stat(filepath.Join(filepath.Dir(dir), "config.toml")); err == nil {
		t.Error("expected no transfer saved outside dir")
	}
}

// TestDownloadFileSendError ensures that a transfer whose acknowledgement
// fails returns the error and leaves nothing behind.
func TestDownloadFileSendError(t *testing.T) {
	dir := t.TempDir()
	sendErr := errors.New("stream closed")
	if _, err := download(dir, &fakeStream{chunks: chunks("a", "b", "c"), sendErr: sendErr}); !errors.Is(err, sendErr) {
		t.Errorf("expected %v, got %v", sendErr, err)
	}
	expectOnly(t, dir)
}

// TestCheckFilename ensures that only plain file names are accepted.
func TestCheckFilename(t *testing.T) {
	for _, name := range []string{"mission.json", "yolo.pt", ".hidden", "a b", "..a"} {
		if err := CheckFilename(name); err != nil {
			t.Errorf("expected %q accepted, got %v", name, err)
		}
	}
	for _, name := range []string{"", ".", "..", "a/b", "/a", "../a", `a\b`, "a\x00b"} {
		if err := CheckFilename(name); status.Code(err) != codes.InvalidArgument {
			t.Errorf("expected %q rejected with InvalidArgument, got %v", name, err)
		}
	}
}
