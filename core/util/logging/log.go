package logging

import (
	"errors"
	"net"
	"net/http"
	"os"
	"strconv"
	"sync/atomic"
	"time"

	logdyhttp "github.com/logdyhq/logdy-core/http"
	"github.com/logdyhq/logdy-core/logdy"
	"github.com/logdyhq/logdy-core/modes"
	"github.com/nxadm/tail"
)

// Batch messages into large, infrequent websocket frames so slow, high
// latency links aren't flooded with small writes
const bulkWindowMs = 1000

// Cap the in-memory buffer so a client catching up after a stall doesn't
// pull an unbounded backlog
const maxMessageCount = 10_000

// How long AddFile waits for a file to appear, and how often it checks
const fileWaitTimeout = 30 * time.Second
const fileWaitInterval = 500 * time.Millisecond

// logdy registers part of its UI on the global mux, so initializing it twice
// panics
var started atomic.Bool

// Logger serves a logdy web UI for the files added to it. logdy keeps its
// state in package globals, so only one Logger may exist per process.
type Logger struct {
	logdy  logdy.Logdy
	server *http.Server
}

// NewLogServer starts a logdy web UI listening on the given bind address and
// port.
func NewLogServer(addr string, port int) (*Logger, error) {
	if !started.CompareAndSwap(false, true) {
		return nil, errors.New("log server already started")
	}
	mux := http.NewServeMux()
	// Leave ServerIp/ServerPort unset so logdy registers on our mux instead of
	// starting its own server, which panics on a bind error
	l := logdy.InitializeLogdy(logdy.Config{
		BulkWindowMs:    bulkWindowMs,
		MaxMessageCount: maxMessageCount,
		LogLevel:        logdy.LOG_LEVEL_SILENT,
	}, mux)
	// logdy tails files without setting a logger, so tail falls back to its
	// default stderr logger and reports every truncation and reopen
	tail.DefaultLogger = tail.DiscardingLogger

	listener, err := net.Listen("tcp", net.JoinHostPort(addr, strconv.Itoa(port)))
	if err != nil {
		return nil, err
	}
	server := &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: 30 * time.Second,
	}
	go server.Serve(listener)

	return &Logger{logdy: l, server: server}, nil
}

// AddFile starts a goroutine that makes logdy tail the file at path, starting
// from its end. If the file does not appear within 30 seconds, the goroutine
// exits without tailing it. It does nothing on a nil Logger.
func (l *Logger) AddFile(path string) {
	if l == nil {
		return
	}
	go func() {
		deadline := time.Now().Add(fileWaitTimeout)
		for {
			_, err := os.Stat(path)
			if err == nil {
				break
			}
			if !errors.Is(err, os.ErrNotExist) || time.Now().After(deadline) {
				return
			}
			time.Sleep(fileWaitInterval)
		}
		modes.FollowFiles(logdyhttp.Ch, []string{path})
	}()
}

// Close stops the web UI. It does nothing on a nil Logger.
func (l *Logger) Close() error {
	if l == nil {
		return nil
	}
	return l.server.Close()
}
