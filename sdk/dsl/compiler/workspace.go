// Command compiler's workspace helpers create a scratch Go module that a
// mission's declared imports (plus the base SDK DSL packages) are fetched
// into, so the rest of the compiler can load and build against them.
package compiler

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
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

// basePkgPaths lists the packages EnsureBaseImports adds when a mission's
// own Import stanza doesn't already mention them.
var basePkgPaths = []string{dslPkgPath, dslActionsPkgPath, dslEventsPkgPath, dslTypesPkgPath}

// EnsureBaseImports returns imports with one *parser.ImportSpec appended
// entry of basePkgPaths not already present (matched by Path alone,
// ignoring alias/version), each added unaliased so it resolves to its
// package's own name.
func EnsureBaseImports(imports []*parser.ImportSpec) []*parser.ImportSpec {
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

// NewWorkspace creates a scratch directory containing a throwaway Go
// module, then fetches every one of imports into it with "go get" (pinned
// to Version when one was given, otherwise "latest"). If steeleagleRef is
// non-empty, it overrides the version used for every import under
// SteeleagleModule (base SDK packages and any mission-declared import of a
// steeleagle package alike), regardless of any Version the import already
// carries.
func NewWorkspace(imports []*parser.ImportSpec, steeleagleRef string, overridePaths []string) (dir string, cleanup func(), err error) {
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

	overrides, err := resolveOverrides(overridePaths)
	if err != nil {
		cleanup()
		return "", nil, err
	}
	for mod, path := range overrides {
		// A placeholder require paired with a replace needs no network
		// access to resolve: go build reads path's content directly.
		if out, err := runIn(dir, "go", "mod", "edit",
			"-require="+mod+"@v0.0.0-00010101000000-000000000000",
			"-replace="+mod+"="+path); err != nil {
			cleanup()
			return "", nil, fmt.Errorf("go mod edit -replace=%s=%s: %w\n%s", mod, path, err, out)
		}
	}

	for _, imp := range imports {
		if _, ok := overriddenBy(imp.Path, overrides); ok {
			continue // satisfied by a local override above, not fetched
		}
		version := imp.Version
		if steeleagleRef != "" && isSteeleaglePkg(imp.Path) {
			version = steeleagleRef
		} else if version == "" {
			version = "latest"
		}
		if out, err := runIn(dir, "go", "get", imp.Path+"@"+version); err != nil {
			cleanup()
			return "", nil, fmt.Errorf("go get %s@%s: %w\n%s", imp.Path, version, err, out)
		}
	}

	if err := localizeSteeleagleModule(dir); err != nil {
		cleanup()
		return "", nil, err
	}

	return dir, cleanup, nil
}

// isSteeleaglePkg reports whether path is SteeleagleModule itself or a
// package beneath it.
func isSteeleaglePkg(path string) bool {
	return path == SteeleagleModule || strings.HasPrefix(path, SteeleagleModule+"/")
}

// expandOverridePath expands a leading "~" (as in an OverrideSpec written
// "~/some/dir") to the current user's home directory, then resolves the
// result to an absolute path.
func expandOverridePath(path string) (string, error) {
	if path == "~" || strings.HasPrefix(path, "~/") {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("resolving home directory for %q: %w", path, err)
		}
		path = filepath.Join(home, strings.TrimPrefix(path, "~"))
	}
	return filepath.Abs(path)
}

// resolveOverrides expands each of paths (an Override stanza's raw
// directory strings) and resolves the module each one declares in its own
// go.mod, returning a map from that module path to the directory's
// absolute path.
func resolveOverrides(paths []string) (map[string]string, error) {
	if len(paths) == 0 {
		return nil, nil
	}
	overrides := make(map[string]string, len(paths))
	for _, p := range paths {
		abs, err := expandOverridePath(p)
		if err != nil {
			return nil, fmt.Errorf("override %q: %w", p, err)
		}
		out, err := runIn(abs, "go", "list", "-m")
		if err != nil {
			return nil, fmt.Errorf("resolving module for override %q: %w\n%s", p, err, out)
		}
		overrides[strings.TrimSpace(out)] = abs
	}
	return overrides, nil
}

// overriddenBy reports whether pkgPath is, or is a package beneath, one of
// overrides' module paths, returning that module path if so.
func overriddenBy(pkgPath string, overrides map[string]string) (string, bool) {
	for mod := range overrides {
		if pkgPath == mod || strings.HasPrefix(pkgPath, mod+"/") {
			return mod, true
		}
	}
	return "", false
}

// commitSHARe matches a full or abbreviated git commit hash.
var commitSHARe = regexp.MustCompile(`^[0-9a-fA-F]{7,40}$`)

// ResolveSteeleagleRef resolves ref (a branch, tag, or commit SHA) to a
// commit SHA in the SteelEagle repository, for use as -steeleagle-ref.
//
// go get's own "@<branch>" version query goes through the Go module proxy,
// which caches its answer to "what commit is this branch/tag currently at"
// and can lag behind the repository's real tip on a fast-moving branch
// (observed: the proxy returned a commit three pushes behind the actual
// v4.0-beta tip). Resolving the ref ourselves with "git ls-remote" asks the
// repository directly, then "go get module@<sha>" pins to that exact,
// unambiguous commit, which every proxy resolves consistently.
//
// If ref already looks like a commit SHA, it's returned as-is: ls-remote
// only resolves refs (branches/tags) advertised by the server, not
// arbitrary commit hashes.
func ResolveSteeleagleRef(ref string) (string, error) {
	if commitSHARe.MatchString(ref) {
		return ref, nil
	}

	repoURL := "https://" + SteeleagleModule
	out, err := exec.Command("git", "ls-remote", repoURL, ref).Output()
	if err != nil {
		return "", fmt.Errorf("git ls-remote %s %s: %w", repoURL, ref, err)
	}
	line := strings.SplitN(strings.TrimSpace(string(out)), "\n", 2)[0]
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return "", fmt.Errorf("ref %q not found in %s", ref, repoURL)
	}
	return fields[0], nil
}

// localizeSteeleagleModule copies the fetched SteeleagleModule out of the
// (read-only, content-addressed) module cache and into workspace, then adds
// a "replace" directive pointing the module at the copy. CreateOverlay keys
// its replacements by each package's on-disk GoFiles path, and the "go"
// command refuses -overlay replacements for any file beneath GOMODCACHE
// (https://pkg.go.dev/cmd/go#hdr-Compile_packages_and_dependencies), so the
// module being scrubbed/const-generated must resolve to a path outside it.
func localizeSteeleagleModule(workspace string) error {
	out, err := runIn(workspace, "go", "list", "-m", "-f", "{{.Dir}}", SteeleagleModule)
	if err != nil {
		return fmt.Errorf("locating %s module: %w\n%s", SteeleagleModule, err, out)
	}
	modDir := strings.TrimSpace(out)

	localDir := filepath.Join(workspace, ".steeleagle-src")
	if err := os.CopyFS(localDir, os.DirFS(modDir)); err != nil {
		return fmt.Errorf("copying %s module: %w", SteeleagleModule, err)
	}

	if out, err := runIn(workspace, "go", "mod", "edit", "-replace="+SteeleagleModule+"="+localDir); err != nil {
		return fmt.Errorf("go mod edit -replace: %w\n%s", err, out)
	}
	return nil
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

// MaterializeOverlay writes overlay's replacement file contents to disk
// under workspace and returns the path to a -overlay JSON file describing
// them, so a subsequent "go build"/"go vet" sees the scrubbed and
// const-generated source rather than what's actually on disk. Returns ""
// if overlay is empty (nothing to scrub/generate).
func MaterializeOverlay(workspace string, overlay map[string][]byte) (string, error) {
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

// TidyAndBuild runs "go mod tidy" and then "go build" in workspace,
// producing outPath (an absolute path, since workspace's own directory is
// discarded once the compiler exits). overlayPath, if non-empty, is passed
// as -overlay so the build sees the scrubbed/const-generated SDK source
// rather than what CreateOverlay left untouched on disk. If arch is
// non-empty, GOARCH=arch is set for the build so it cross-compiles.
func TidyAndBuild(workspace, overlayPath, outPath, arch string) error {
	tidyArgs := []string{"mod", "tidy"}
	if overlayPath != "" {
		tidyArgs = append(tidyArgs, "-overlay="+overlayPath)
	}
	if out, err := runIn(workspace, "go", tidyArgs...); err != nil {
		return fmt.Errorf("go mod tidy: %w\n%s", err, out)
	}

	// -s -w strip the symbol table and DWARF debug info to minimize binary
	// size; -trimpath drops build-machine file paths from the result.
	// CGO_ENABLED=0 forces a statically linked binary with no dependency on
	// the host's C library, so it runs unmodified on whatever it's shipped to.
	buildArgs := []string{"build", "-trimpath", "-ldflags=-s -w", "-o", outPath}
	if overlayPath != "" {
		buildArgs = append(buildArgs, "-overlay="+overlayPath)
	}
	buildArgs = append(buildArgs, ".")
	cmd := exec.Command("go", buildArgs...)
	cmd.Dir = workspace
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if arch != "" {
		cmd.Env = append(cmd.Env, "GOARCH="+arch)
	}
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("go build: %w\n%s", err, out)
	}
	return nil
}

// AbsOutPath resolves out (as given on the command line) to an absolute
// path, so it still lands in the caller's original working directory once
// builds run with Dir set to the scratch workspace.
func AbsOutPath(out string) (string, error) {
	return filepath.Abs(out)
}
