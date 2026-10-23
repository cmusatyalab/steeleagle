// Package tools builds Go programs against the SteelEagle SDK
// preprocessed for a vehicle, scrubbed according to its cap file, with
// constants generated from a mission's manifest and GeoJSON.
package buildtools

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"github.com/cmusatyalab/steeleagle/sdk/preprocess"
)

// DefaultEnv returns the environment SDK builds run with by default, on
// top of the process's. Cgo is disabled so binaries are static, which run
// on vehicles whatever their C library and cross-compile without a C
// toolchain.
func DefaultEnv() []string {
	return []string{"CGO_ENABLED=0"}
}

// BuildSdk builds the packages matching patterns (the package in dir if
// none are given, as for go build) in the Go module at dir with go build.
// The build overlays the packages of the module at dir (or, in a go.work
// workspace, of every workspace module) and of the SDK's module.
func BuildSdk(dir string, patterns []string, options ...Option) []*CompileError {
	c, errs := NewConfig(options...)
	if len(errs) > 0 {
		return errs
	}
	cfg, errs := c.OverlayConfig()
	if len(errs) > 0 {
		return errs
	}
	if len(patterns) == 0 {
		patterns = []string{"."}
	}
	env := DefaultEnv()
	cfg.Dir, cfg.Env = dir, env

	// The local modules, which go list -m lists one per line
	out, err := goCmd(dir, env, "list", "-m")
	if err != nil {
		return []*CompileError{{Err: err}}
	}
	cfg.Modules = strings.Fields(string(out))

	overlay, preErrs := preprocess.CreateOverlay(cfg, patterns...)
	if len(preErrs) > 0 {
		return CompileErrors(preErrs)
	}
	build := []string{"build"}
	if c.OutputFile != "" {
		path, err := filepath.Abs(c.OutputFile)
		if err != nil {
			return []*CompileError{{Err: err}}
		}
		build = append(build, "-o", path)
	}
	if len(overlay) > 0 {
		// The overlay goes in a temporary directory, not the module
		tmp, err := os.MkdirTemp("", "steeleagle-overlay-*")
		if err != nil {
			return []*CompileError{{Err: err}}
		}
		defer os.RemoveAll(tmp)
		overlayJson, err := preprocess.WriteOverlay(tmp, overlay)
		if err != nil {
			return []*CompileError{{Err: err}}
		}
		build = append(build, "-overlay="+overlayJson)
	}
	build = append(build, patterns...)
	if _, err := goCmd(dir, env, build...); err != nil {
		return []*CompileError{{Err: err}}
	}
	return nil
}

// goCmd runs the go tool in dir with env on top of the process's
// environment and returns its standard output, folding its combined
// output into the returned error.
func goCmd(dir string, env []string, args ...string) ([]byte, error) {
	cmd := exec.Command("go", args...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), env...)
	var stdout bytes.Buffer
	var combined lockedBuffer
	// os/exec copies stdout and stderr in separate goroutines, since they
	// are different writers, so combined must be safe for concurrent use
	cmd.Stdout = io.MultiWriter(&stdout, &combined)
	cmd.Stderr = &combined
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("go %v: %w\n%s", args, err, combined.Bytes())
	}
	return stdout.Bytes(), nil
}

// lockedBuffer is a bytes.Buffer that is safe for concurrent writes.
type lockedBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

// Write appends p to the buffer.
func (b *lockedBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

// Bytes returns the buffer's contents.
func (b *lockedBuffer) Bytes() []byte {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Bytes()
}
