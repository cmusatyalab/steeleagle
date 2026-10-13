package compiler

import (
	"bytes"
	"cmp"
	"encoding/json"
	"fmt"
	"go/version"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"slices"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/linker"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
	"github.com/cmusatyalab/steeleagle/sdk/preprocess"
	"golang.org/x/mod/modfile"
	"golang.org/x/mod/module"
)

// Workspace is a Go module directory missions are compiled in, along with
// the environment every go command and package load in it runs with. A
// workspace can be reused for many compiles, but not by concurrent ones.
// Each compile or load starts from the go.mod NewWorkspace created, so one
// mission's modules never leak into the next.
type Workspace struct {
	Dir string   // workspace directory
	Env []string // environment for every go command and package load, on top of the process's

	initMod []byte // go.mod as NewWorkspace created it, nil if it didn't
}

// NewWorkspace creates a temporary workspace directory initialized as the
// "mission" Go module. Its go commands and package loads run with
// buildtools.DefaultEnv followed by env, so env can override the defaults, and can
// set e.g. GOOS and GOARCH to cross-compile. The caller must Close the
// workspace when done.
func NewWorkspace(env []string) (*Workspace, error) {
	tmp, err := os.MkdirTemp("", "steeleagle-mission-*")
	if err != nil {
		return nil, err
	}
	w := &Workspace{Dir: tmp, Env: append(buildtools.DefaultEnv(), env...)}
	if err := w.goCmd("mod", "init", "mission"); err != nil {
		os.RemoveAll(tmp)
		return nil, fmt.Errorf("module init failed: %w", err)
	}
	if w.initMod, err = os.ReadFile(filepath.Join(tmp, "go.mod")); err != nil {
		os.RemoveAll(tmp)
		return nil, err
	}
	return w, nil
}

// resetModule restores the workspace's go.mod to the one NewWorkspace
// created, removing every requirement and replacement earlier compiles and
// loads added. go.sum is kept: its checksums stay correct, and keeping
// them saves the go tool looking them up again. A workspace not created by
// NewWorkspace is left as it is.
func (w *Workspace) resetModule() error {
	if w.initMod == nil {
		return nil
	}
	return os.WriteFile(filepath.Join(w.Dir, "go.mod"), w.initMod, 0o644)
}

// Close removes the workspace directory.
func (w *Workspace) Close() {
	os.RemoveAll(w.Dir)
}

// Compile compiles a mission from src (see FromFile, FromSource and
// FromJson) into a binary, in a temporary workspace with the default
// environment.
func Compile(src Source, options ...buildtools.Option) []*buildtools.CompileError {
	m, errs := newMission(src, options)
	if len(errs) > 0 {
		return errs
	}
	w, err := NewWorkspace(nil)
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	defer w.Close()
	return w.compile(m)
}

// Load loads the types available to a mission from src (see FromFile,
// FromSource and FromJson), without linking the mission, in a temporary
// workspace with the default environment. It returns the type registry in
// JSON format.
func Load(src Source, options ...buildtools.Option) ([]byte, []*buildtools.CompileError) {
	m, errs := newMission(src, options)
	if len(errs) > 0 {
		return nil, errs
	}
	w, err := NewWorkspace(nil)
	if err != nil {
		return nil, []*buildtools.CompileError{{Err: err}}
	}
	defer w.Close()
	return w.loadJson(m)
}

// Compile compiles a mission from src (see FromFile, FromSource and
// FromJson) into a binary in this workspace.
func (w *Workspace) Compile(src Source, options ...buildtools.Option) []*buildtools.CompileError {
	m, errs := newMission(src, options)
	if len(errs) > 0 {
		return errs
	}
	return w.compile(m)
}

// Load loads the types available to a mission from src (see FromFile,
// FromSource and FromJson) in this workspace, without linking the
// mission, and returns the type registry in JSON format.
func (w *Workspace) Load(src Source, options ...buildtools.Option) ([]byte, []*buildtools.CompileError) {
	m, errs := newMission(src, options)
	if len(errs) > 0 {
		return nil, errs
	}
	return w.loadJson(m)
}

// mission is a parsed mission along with the build configuration it is
// compiled with.
type mission struct {
	ast *parser.Ast
	cfg *buildtools.Config
}

// newMission parses a mission from src, applies and parses options, and
// checks the mission's role against the manifest.
func newMission(src Source, options []buildtools.Option) (*mission, []*buildtools.CompileError) {
	ast, err := parseMission(src)
	if err != nil {
		return nil, []*buildtools.CompileError{{Err: err}}
	}
	cfg, errs := buildtools.NewConfig(options...)
	if len(errs) > 0 {
		return nil, errs
	}
	if err := checkRole(ast.Role, cfg.Manifest); err != nil {
		return nil, []*buildtools.CompileError{err}
	}
	return &mission{ast: ast, cfg: cfg}, nil
}

// checkRole reports an error unless role, if the mission has one, is
// declared by the manifest.
func checkRole(role *parser.RoleStanza, manifest *sdk.ManifestFile) *buildtools.CompileError {
	if role.Name == "" {
		return nil
	}
	if manifest == nil || !slices.Contains(manifest.Info.Roles, role.Name) {
		return &buildtools.CompileError{
			Err:    fmt.Errorf("role %s is not declared in the manifest", role.Name),
			File:   role.Pos.Filename,
			Decl:   role.Name,
			LineNo: uint32(role.Pos.Line),
		}
	}
	return nil
}

// compile links m against its type registry, generates the mission script
// using the mission template, and then builds it using go build to the
// output destination.
func (w *Workspace) compile(m *mission) []*buildtools.CompileError {
	// Load types
	registry, overlay, errs := w.load(m)
	if len(errs) > 0 {
		return errs
	}
	// Link against the registry
	ir, errs := linker.Link(m.ast, registry)
	if len(errs) > 0 {
		return errs
	}
	if err := generate(ir, m.cfg, w.Dir); err != nil {
		return []*buildtools.CompileError{{Err: err, File: "main.go"}}
	}
	output := cmp.Or(m.cfg.OutputFile, outputDefault)
	path, err := filepath.Abs(output)
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	// Build with the loader's flags, so the build reuses the dependencies
	// it already compiled
	build := append([]string{"build"}, loader.BuildFlags()...)
	build = append(build, "-o", path)
	if len(overlay) > 0 {
		overlayJson, err := preprocess.WriteOverlay(filepath.Join(w.Dir, overlayDir), overlay)
		if err != nil {
			return []*buildtools.CompileError{{Err: err}}
		}
		build = append(build, "-overlay="+overlayJson)
	}
	for _, args := range [][]string{{"mod", "tidy"}, build} {
		if err := w.goCmd(args...); err != nil {
			return []*buildtools.CompileError{{Err: err, File: "main.go"}}
		}
	}
	return nil
}

// load installs the modules m needs into a fresh go.mod, creates the
// overlay for its cap, manifest, and GeoJson, then loads all available
// types, returning the corresponding registry and the overlay they were
// loaded with.
func (w *Workspace) load(m *mission) (*loader.TypeRegistry, map[string][]byte, []*buildtools.CompileError) {
	ast := m.ast

	// Check the cap, manifest, and GeoJson before downloading anything
	cfg, errs := m.cfg.OverlayConfig()
	if len(errs) > 0 {
		return nil, nil, errs
	}

	// Install all modules, starting from the go.mod NewWorkspace created
	if err := w.resetModule(); err != nil {
		return nil, nil, []*buildtools.CompileError{{Err: err}}
	}
	if err := w.installModules(withSdk(ast.Modules.Modules)); err != nil {
		return nil, nil, []*buildtools.CompileError{{Err: err}}
	}

	// Overlay the import graph of the mission and of main.go.tmpl, only
	// for packages in the SDK and the listed modules (scrubbing every
	// external dependency would only slow the build down)
	paths := linker.FixedImportPaths()
	requests := []*loader.PackageRequest{}
	for _, imp := range ast.Imports.Imports {
		paths = append(paths, imp.Path)
		requests = append(requests, &loader.PackageRequest{
			Path:  imp.Path,
			Alias: imp.Alias,
			Pos:   imp.Pos,
		})
	}
	cfg.Dir, cfg.Env = w.Dir, w.Env
	// -mod=mod lets the load add missing requirements to go.mod, and is
	// passed as a flag so a GOFLAGS in the environment can't drop it
	cfg.BuildFlags = []string{"-mod=mod"}
	for _, mod := range ast.Modules.Modules {
		cfg.Modules = append(cfg.Modules, mod.Path)
	}
	overlay, preErrs := preprocess.CreateOverlay(cfg, paths...)
	if len(preErrs) > 0 {
		return nil, nil, buildtools.CompileErrors(preErrs)
	}

	registry, errs := loader.LoadTypes(requests, w.Dir, overlay, w.Env)
	if len(errs) > 0 {
		return nil, nil, errs
	}
	return registry, overlay, nil
}

// loadJson loads the types available to m and returns the type registry
// in JSON format.
func (w *Workspace) loadJson(m *mission) ([]byte, []*buildtools.CompileError) {
	registry, _, errs := w.load(m)
	if len(errs) > 0 {
		return nil, errs
	}
	out, err := registry.ToJson()
	if err != nil {
		return nil, []*buildtools.CompileError{{Err: fmt.Errorf("encoding type registry: %w", err)}}
	}
	return out, nil
}

// installModules requires every module in modules in the workspace's
// go.mod, replacing each with a local directory: its override, or
// otherwise a copy of the module downloaded at its version ("latest" if it
// has none). Only the modules themselves are looked up, never modules at
// prefixes of their paths. Each module's files must live outside the
// module cache, since go build refuses to overlay files inside it. The
// workspace's go version is raised to the highest any module requires.
func (w *Workspace) installModules(modules []*parser.ModuleSpec) error {
	for _, mod := range modules {
		dir, version := mod.Override, cmp.Or(mod.Version, placeholderVersion(mod.Path))
		if dir == "" {
			var err error
			if dir, version, err = w.downloadModule(mod.Path, cmp.Or(mod.Version, "latest")); err != nil {
				if mod.Path == sdkModPath && mod.Version == "" {
					return fmt.Errorf("the SDK module %s is not listed in Modules:, so its latest version is used: %w", sdkModPath, err)
				}
				return err
			}
		}
		err := w.goCmd(
			"mod", "edit",
			"-require="+mod.Path+"@"+version,
			"-replace="+mod.Path+"="+dir,
		)
		if err != nil {
			return err
		}
		if !filepath.IsAbs(dir) {
			dir = filepath.Join(w.Dir, dir)
		}
		if err := w.raiseGoVersion(filepath.Join(dir, "go.mod")); err != nil {
			return err
		}
	}
	return nil
}

// withSdk returns modules, with the SDK's module added at its latest
// version if modules don't list it, since every mission builds against it.
func withSdk(modules []*parser.ModuleSpec) []*parser.ModuleSpec {
	if slices.ContainsFunc(modules, func(m *parser.ModuleSpec) bool { return m.Path == sdkModPath }) {
		return modules
	}
	return append(slices.Clone(modules), &parser.ModuleSpec{Path: sdkModPath})
}

// downloadModule downloads the module at path at version, which may be any
// version query go mod download accepts (e.g. "latest" or a branch), and
// copies it out of the module cache into the workspace's modulesDir, unless
// an earlier compile already did. It returns the directory of the copy, as
// a path relative to the workspace, and the version the query resolved to.
func (w *Workspace) downloadModule(path, version string) (string, string, error) {
	out, err := w.goOutput("mod", "download", "-json", path+"@"+version)
	var dl struct{ Version, Dir, Error string }
	if jsonErr := json.Unmarshal(out, &dl); jsonErr != nil || dl.Error != "" || err != nil {
		if dl.Error != "" {
			return "", "", fmt.Errorf("downloading module %s@%s: %s", path, version, dl.Error)
		}
		return "", "", fmt.Errorf("downloading module %s@%s: %w", path, version, cmp.Or(err, jsonErr))
	}
	escPath, err := module.EscapePath(path)
	if err != nil {
		return "", "", err
	}
	escVersion, err := module.EscapeVersion(dl.Version)
	if err != nil {
		return "", "", err
	}
	rel := filepath.Join(modulesDir, escPath+"@"+escVersion)
	dst := filepath.Join(w.Dir, rel)
	if _, err := os.Stat(dst); err != nil {
		// Module versions never change, so a copy only needs making once.
		// It's made beside its destination and renamed into place, so an
		// interrupted copy is never mistaken for a complete one
		if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
			return "", "", err
		}
		tmp, err := os.MkdirTemp(filepath.Dir(dst), ".tmp-*")
		if err != nil {
			return "", "", err
		}
		defer os.RemoveAll(tmp)
		if err := copyDir(dl.Dir, tmp); err != nil {
			return "", "", fmt.Errorf("copying module %s@%s: %w", path, dl.Version, err)
		}
		if err := os.Rename(tmp, dst); err != nil {
			return "", "", err
		}
	}
	return "./" + filepath.ToSlash(rel), dl.Version, nil
}

// copyDir copies the directory tree src to dst, which must exist, making
// every copy writable (the module cache's files are read-only).
func copyDir(src, dst string) error {
	return filepath.WalkDir(src, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, data, 0o644)
	})
}

// raiseGoVersion raises the go version in the workspace's go.mod to the
// one the go.mod at modFile requires, if that is higher, so later go
// commands switch to a toolchain new enough to build the module.
func (w *Workspace) raiseGoVersion(modFile string) error {
	want, err := goVersion(modFile)
	if err != nil {
		return err
	}
	have, err := goVersion(filepath.Join(w.Dir, "go.mod"))
	if err != nil {
		return err
	}
	if want == "" || version.Compare("go"+want, "go"+have) <= 0 {
		return nil
	}
	return w.goCmd("mod", "edit", "-go="+want)
}

// goVersion returns the go version the go.mod at path declares, or "" if
// it declares none.
func goVersion(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	f, err := modfile.ParseLax(path, data, nil)
	if err != nil {
		return "", err
	}
	if f.Go == nil {
		return "", nil
	}
	return f.Go.Version, nil
}

// placeholderVersion returns the lowest version go.mod accepts for a module
// at path (v0.0.0, or vN.0.0 for a /vN major version suffix). It is used to
// require a module that is replaced by a local directory, where the
// required version is irrelevant but must still be a concrete version.
func placeholderVersion(path string) string {
	if _, major, ok := module.SplitPathVersion(path); ok && major != "" {
		return module.PathMajorPrefix(major) + ".0.0"
	}
	return "v0.0.0"
}

// goCmd runs the go tool inside the workspace, folding its output into
// the returned error.
func (w *Workspace) goCmd(args ...string) error {
	if output, err := w.command(args...).CombinedOutput(); err != nil {
		return fmt.Errorf("go %v: %w\n%s", args, err, output)
	}
	return nil
}

// goOutput runs the go tool inside the workspace and returns its standard
// output, even if the command fails, folding its standard error into the
// returned error.
func (w *Workspace) goOutput(args ...string) ([]byte, error) {
	cmd := w.command(args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		return out, fmt.Errorf("go %v: %w\n%s", args, err, stderr.Bytes())
	}
	return out, nil
}

// command returns a go command that runs in the workspace with its
// environment.
func (w *Workspace) command(args ...string) *exec.Cmd {
	cmd := exec.Command("go", args...)
	cmd.Dir = w.Dir
	cmd.Env = append(os.Environ(), w.Env...)
	return cmd
}
