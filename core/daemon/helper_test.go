package daemon

import (
	"io"
	"os"
	"testing"

	"github.com/rs/zerolog"
)

// testOutput returns stdout when tests are verbose, and discards output
// otherwise.
func testOutput() io.Writer {
	if testing.Verbose() {
		return os.Stdout
	}
	return io.Discard
}

// testLogger returns a logger that only logs when tests are verbose.
func testLogger() zerolog.Logger {
	if testing.Verbose() {
		return zerolog.New(os.Stdout).With().Timestamp().Logger()
	}
	return zerolog.Nop()
}
