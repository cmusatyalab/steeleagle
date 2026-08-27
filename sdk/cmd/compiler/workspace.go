// Command compiler's workspace helpers create a scratch Go module that a
// mission's declared imports (plus the base SDK DSL packages) are fetched
// into, so the rest of the compiler can load and build against them.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
)

// Base SDK packages every generated mission needs regardless of what the
// mission itself declares: dsl for the Action/Event/Datatype interfaces and
// MissionData, and actions/events/types for the primitives most missions
// build on.
const (
	dslPkgPath        = "github.com/cmusatyalab/steeleagle/sdk/dsl"
	dslActionsPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
	dslEventsPkgPath  = "github.com/cmusatyalab/steeleagle/sdk/dsl/events"
	dslTypesPkgPath   = "github.com/cmusatyalab/steeleagle/sdk/dsl/types"
)

// basePkgPaths lists the packages ensureBaseImports adds when a mission's
// own Import stanza doesn't already mention them.
var basePkgPaths = []string{dslPkgPath, dslActionsPkgPath, dslEventsPkgPath, dslTypesPkgPath}

// ensureBaseImports returns imports with one *parser.ImportSpec appended
// per entry of basePkgPaths not already present (matched by Path alone,
// ignoring alias/version), each added unaliased so it resolves to its
// package's own name.
func ensureBaseImports(imports []*parser.ImportSpec) []*parser.ImportSpec {
	have := make(map[string]bool, len(imports))
	for _, imp := range imports {
		have[imp.Path] = true
	}
	out := imports
	for _, path := range basePkgPaths {
		if !have[path] {
			out = append(out, &parser.ImportSpec{Path: path})
		}
	}
	return out
}

// newWorkspace creates a scratch directory containing a throwaway Go
// module, then fetches every one of imports into it with "go get" (pinned
// to Version when one was given, otherwise "latest"). The caller is
// responsible for calling the returned cleanup once the workspace is no
// longer needed.
func newWorkspace(imports []*parser.ImportSpec) (dir string, cleanup func(), err error) {
	dir, err = os.MkdirTemp("", "steeleagle-mission-*")
	if err != nil {
		return "", nil, fmt.Errorf("creating workspace: %w", err)
	}
	cleanup = func() { os.RemoveAll(dir) }

	goVersion := strings.TrimPrefix(runtime.Version(), "go")
	if out, err := runIn(dir, "go", "mod", "init", "steeleagle-mission"); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("go mod init: %w\n%s", err, out)
	}
	if out, err := runIn(dir, "go", "mod", "edit", "-go="+goVersion); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("go mod edit: %w\n%s", err, out)
	}

	for _, imp := range imports {
		version := imp.Version
		if version == "" {
			version = "latest"
		}
		if out, err := runIn(dir, "go", "get", imp.Path+"@"+version); err != nil {
			cleanup()
			return "", nil, fmt.Errorf("go get %s@%s: %w\n%s", imp.Path, version, err, out)
		}
	}

	return dir, cleanup, nil
}

// runIn runs name with args in dir, returning its combined output for
// error reporting.
func runIn(dir, name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	return string(out), err
}

// overlayFile is the JSON structure the "go" command's -overlay flag reads:
// a map from a real, on-disk source file to the file whose content should
// be used in its place.
type overlayFile struct {
	Replace map[string]string `json:"Replace"`
}

// materializeOverlay writes overlay's replacement file contents to disk
// under workspace and returns the path to a -overlay JSON file describing
// them, so a subsequent "go build"/"go vet" sees the scrubbed and
// const-generated source rather than what's actually on disk. Returns ""
// if overlay is empty (nothing to scrub/generate).
func materializeOverlay(workspace string, overlay map[string][]byte) (string, error) {
	if len(overlay) == 0 {
		return "", nil
	}
	replaceDir := filepath.Join(workspace, ".overlay")
	if err := os.MkdirAll(replaceDir, 0o755); err != nil {
		return "", fmt.Errorf("creating overlay dir: %w", err)
	}

	replace := make(map[string]string, len(overlay))
	i := 0
	for original, content := range overlay {
		i++
		replacement := filepath.Join(replaceDir, fmt.Sprintf("%d_%s", i, filepath.Base(original)))
		if err := os.WriteFile(replacement, content, 0o644); err != nil {
			return "", fmt.Errorf("writing overlay content for %s: %w", original, err)
		}
		replace[original] = replacement
	}

	data, err := json.Marshal(overlayFile{Replace: replace})
	if err != nil {
		return "", fmt.Errorf("marshaling overlay: %w", err)
	}
	overlayPath := filepath.Join(workspace, "overlay.json")
	if err := os.WriteFile(overlayPath, data, 0o644); err != nil {
		return "", fmt.Errorf("writing overlay.json: %w", err)
	}
	return overlayPath, nil
}

// tidyAndBuild runs "go mod tidy" and then "go build" in workspace,
// producing outPath (an absolute path, since workspace's own directory is
// discarded once the compiler exits). overlayPath, if non-empty, is passed
// as -overlay so the build sees the scrubbed/const-generated SDK source
// rather than what CreateOverlay left untouched on disk. If arch is
// non-empty, GOARCH=arch is set for the build so it cross-compiles.
func tidyAndBuild(workspace, overlayPath, outPath, arch string) error {
	tidyArgs := []string{"mod", "tidy"}
	if overlayPath != "" {
		tidyArgs = append(tidyArgs, "-overlay="+overlayPath)
	}
	if out, err := runIn(workspace, "go", tidyArgs...); err != nil {
		return fmt.Errorf("go mod tidy: %w\n%s", err, out)
	}

	buildArgs := []string{"build", "-o", outPath}
	if overlayPath != "" {
		buildArgs = append(buildArgs, "-overlay="+overlayPath)
	}
	buildArgs = append(buildArgs, ".")
	cmd := exec.Command("go", buildArgs...)
	cmd.Dir = workspace
	cmd.Env = os.Environ()
	if arch != "" {
		cmd.Env = append(cmd.Env, "GOARCH="+arch)
	}
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("go build: %w\n%s", err, out)
	}
	return nil
}

// absOutPath resolves out (as given on the command line) to an absolute
// path, so it still lands in the caller's original working directory once
// builds run with Dir set to the scratch workspace.
func absOutPath(out string) (string, error) {
	return filepath.Abs(out)
}
