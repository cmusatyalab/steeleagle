package compiler

import (
	"cmp"
	"fmt"
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

// installModules installs a set of Go modules using "go get"
// in the compiler's workspace.
func (w *Workspace) installModules(modules []*parser.ModuleSpec) error {
	// Require overridden modules and replace them with their local
	// directory, then go get every module. For an overridden module, go get
	// resolves the replacement, which raises the workspace's go version
	// (switching toolchains if need be) to what the replacement requires
	for _, mod := range modules {
		version := cmp.Or(mod.Version, "latest")
		if mod.Override != "" {
			version = cmp.Or(mod.Version, placeholderVersion(mod.Path))
			err := w.goCmd(
				"mod", "edit",
				"-require="+mod.Path+"@"+version,
				"-replace="+mod.Path+"="+mod.Override,
			)
			if err != nil {
				return err
			}
		}
		if err := w.goCmd("get", mod.Path+"@"+version); err != nil {
			return err
		}
	}
	return nil
}

// load installs the modules m needs into a fresh go.mod, creates the
// overlay for its cap,
// manifest, and GeoJson, then loads all available types, returning the
// corresponding registry and the overlay they were loaded with.
func (w *Workspace) load(m *mission) (*loader.TypeRegistry, map[string][]byte, []*buildtools.CompileError) {
	ast := m.ast

	// Install all modules, starting from the go.mod NewWorkspace created
	if err := w.resetModule(); err != nil {
		return nil, nil, []*buildtools.CompileError{{Err: err}}
	}
	if err := w.installModules(ast.Modules.Modules); err != nil {
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
	cfg, errs := m.cfg.OverlayConfig()
	if len(errs) > 0 {
		return nil, nil, errs
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
	cmd := exec.Command("go", args...)
	cmd.Dir = w.Dir
	cmd.Env = append(os.Environ(), w.Env...)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("go %v: %w\n%s", args, err, output)
	}
	return nil
}
