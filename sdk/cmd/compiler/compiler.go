// Command compiler compiles a DSL mission file against a vehicle capability
// manifest: it scrubs unsupported types out of the SDK before loading it, then
// links the mission against what's left.
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"

	"github.com/BurntSushi/toml"
	"golang.org/x/mod/modfile"
)

// steeleagleModule is the module path of the repo compiler.go itself lives
// in, which holds every base package in steeleaglePkgs (loader.go).
const steeleagleModule = "github.com/cmusatyalab/steeleagle"

// capFile models the [unsupported] table of a cap.toml vehicle capability
// manifest: the methods, fields, and enum values the vehicle doesn't
// support, named the same way scrub.go's directive tags are (e.g.
// "services/driver/ControlService/Kill").
type capFile struct {
	Unsupported struct {
		Methods []string `toml:"methods"`
		Fields  []string `toml:"fields"`
		Enums   []string `toml:"enums"`
	} `toml:"unsupported"`
}

// loadCap reads and parses path as a cap.toml manifest, returning the union
// of its unsupported methods, fields, and enum values as scrubPackages'
// blacklist.
func loadCap(path string) (map[string]struct{}, error) {
	var manifest capFile
	if _, err := toml.DecodeFile(path, &manifest); err != nil {
		return nil, fmt.Errorf("parsing %s: %w", path, err)
	}

	unsupported := make(map[string]struct{})
	for _, id := range manifest.Unsupported.Methods {
		unsupported[id] = struct{}{}
	}
	for _, id := range manifest.Unsupported.Fields {
		unsupported[id] = struct{}{}
	}
	for _, id := range manifest.Unsupported.Enums {
		unsupported[id] = struct{}{}
	}
	return unsupported, nil
}

// findRepoRoot returns the local filesystem directory of the steeleagleModule
// module, so the compiled workspace can "use" it for the base SDK packages
// instead of re-fetching them. It relies on being run with a working
// directory inside (or otherwise resolvable to) the steeleagle repo.
func findRepoRoot() (string, error) {
	out, err := exec.Command("go", "list", "-m", "-f", "{{.Dir}}", steeleagleModule).Output()
	if err != nil {
		return "", fmt.Errorf("locating module %s (run this from within the steeleagle repo): %w", steeleagleModule, err)
	}
	return strings.TrimSpace(string(out)), nil
}

// newWorkspace creates a scratch directory containing a go.mod that
// replaces steeleagleModule (and each overridden module) with its local
// on-disk directory, plus a go.sum copied from repoRoot so those replaced
// modules' already-resolved dependencies need no re-fetching.
//
// A go.mod "replace" is used here rather than a go.work workspace (which
// is what this used to do): go.work's unified build list resurfaces
// google.golang.org/genproto's old, otherwise-pruned module version
// alongside its split google.golang.org/genproto/googleapis/rpc
// replacement -- both present somewhere in the full dependency graph, per
// `go mod why google.golang.org/genproto` run from repoRoot -- and go then
// refuses to build the result as an ambiguous import, even though repoRoot
// alone (a single module, so nothing resurfaces) builds this same
// dependency graph fine. A "replace"-based scratch module is single-module
// too, so it doesn't hit this.
func newWorkspace(repoRoot string, overridden map[string]string) (dir string, cleanup func(), err error) {
	dir, err = os.MkdirTemp("", "steeleagle-dsl-*")
	if err != nil {
		return "", nil, fmt.Errorf("creating workspace: %w", err)
	}
	cleanup = func() { os.RemoveAll(dir) }

	repoMod, err := parseRepoGoMod(repoRoot)
	if err != nil {
		cleanup()
		return "", nil, err
	}

	mf := new(modfile.File)
	if err := mf.AddModuleStmt("steeleagle-dsl-workspace"); err != nil {
		cleanup()
		return "", nil, err
	}
	goVersion := strings.TrimPrefix(runtime.Version(), "go")
	if err := mf.AddGoStmt(goVersion); err != nil {
		cleanup()
		return "", nil, err
	}

	// Copy every one of repoRoot's own requirements verbatim: the scratch
	// module needs an explicit require for anything it (transitively)
	// imports through the replaced steeleagleModule below, not just
	// steeleagleModule itself -- Go's completeness check doesn't infer
	// them from the replacement target's own go.mod.
	for _, r := range repoMod.Require {
		if err := mf.AddRequire(r.Mod.Path, r.Mod.Version); err != nil {
			cleanup()
			return "", nil, err
		}
	}
	if err := addLocalReplace(mf, steeleagleModule, repoRoot); err != nil {
		cleanup()
		return "", nil, err
	}
	// repoRoot's own go.mod replaces its api/go submodule (and possibly
	// others) with a local path (monorepo-style); the scratch module needs
	// the same replaces, rewritten to absolute paths, or it can't resolve
	// them.
	for _, r := range repoMod.Replace {
		if r.New.Version != "" {
			continue // a module@version replace, not a local path
		}
		path := r.New.Path
		if !filepath.IsAbs(path) {
			path = filepath.Join(repoRoot, path)
		}
		if err := addLocalReplace(mf, r.Old.Path, path); err != nil {
			cleanup()
			return "", nil, err
		}
	}
	for mod, path := range overridden {
		if err := addLocalReplace(mf, mod, path); err != nil {
			cleanup()
			return "", nil, err
		}
	}

	mf.Cleanup()
	out, err := mf.Format()
	if err != nil {
		cleanup()
		return "", nil, fmt.Errorf("formatting go.mod: %w", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "go.mod"), out, 0644); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("writing go.mod: %w", err)
	}

	sum, err := os.ReadFile(filepath.Join(repoRoot, "go.sum"))
	if err != nil {
		cleanup()
		return "", nil, fmt.Errorf("reading %s's go.sum: %w", repoRoot, err)
	}
	if err := os.WriteFile(filepath.Join(dir, "go.sum"), sum, 0644); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("writing go.sum: %w", err)
	}

	return dir, cleanup, nil
}

// parseRepoGoMod reads and parses repoRoot's own go.mod.
func parseRepoGoMod(repoRoot string) (*modfile.File, error) {
	src, err := os.ReadFile(filepath.Join(repoRoot, "go.mod"))
	if err != nil {
		return nil, fmt.Errorf("reading %s's go.mod: %w", repoRoot, err)
	}
	mf, err := modfile.Parse("go.mod", src, nil)
	if err != nil {
		return nil, fmt.Errorf("parsing %s's go.mod: %w", repoRoot, err)
	}
	return mf, nil
}

// localRequireVersion is the standard placeholder pseudo-version Go uses
// for a module that's only ever resolved through a "replace" directive,
// never actually published.
const localRequireVersion = "v0.0.0-00010101000000-000000000000"

// addLocalReplace adds a require and an unconditional (version-less)
// replace pointing mod at its local on-disk path, so it applies no matter
// what version of mod anything elsewhere in the graph asks for -- notably
// including repoRoot's own go.mod, once it's pulled in as a dependency via
// the replace this sets up for steeleagleModule itself: replace directives
// aren't transitive, but require directives are, so repoRoot's own
// requirements (e.g. its api/go submodule, at whatever version repoRoot
// itself declares) still show up in the graph and need to resolve too.
func addLocalReplace(mf *modfile.File, mod, path string) error {
	if err := mf.AddRequire(mod, localRequireVersion); err != nil {
		return err
	}
	return mf.AddReplace(mod, "", path, "")
}

// moduleLinePattern matches a go.mod file's "module <path>" declaration.
var moduleLinePattern = regexp.MustCompile(`(?m)^module\s+(\S+)`)

// overriddenModules reads the go.mod of every overridePaths entry and
// returns a map from each declared module path to its on-disk directory,
// so installImports can skip fetching any Import a local Override already
// provides, and newWorkspace can replace that module with its local path.
func overriddenModules(overridePaths []string) (map[string]string, error) {
	modules := make(map[string]string, len(overridePaths))
	for _, p := range overridePaths {
		src, err := os.ReadFile(filepath.Join(p, "go.mod"))
		if err != nil {
			return nil, fmt.Errorf("reading go.mod for override %q: %w", p, err)
		}
		m := moduleLinePattern.FindSubmatch(src)
		if m == nil {
			return nil, fmt.Errorf("override %q: go.mod has no module declaration", p)
		}
		modules[string(m[1])] = p
	}
	return modules, nil
}

// installImports fetches every import that isn't already part of
// steeleagleModule or one of overridden (those resolve locally through the
// workspace's replace of repoRoot/the Override paths) into workspace's
// go.mod, so loadPackages/scrubPackages can find them afterwards. An import
// with a Version is fetched pinned to that version; otherwise the latest
// version is fetched.
func installImports(workspace string, imports []*ImportSpec, overridden map[string]string) error {
	for _, imp := range imports {
		if locallyResolved(imp.Path, steeleagleModule) {
			continue
		}
		skip := false
		for mod := range overridden {
			if locallyResolved(imp.Path, mod) {
				skip = true
				break
			}
		}
		if skip {
			continue
		}

		path := imp.Path
		if imp.Version != "" {
			path += "@" + imp.Version
		}
		cmd := exec.Command("go", "get", path)
		cmd.Dir = workspace
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("go get %s: %w\n%s", path, err, out)
		}
	}
	return nil
}

// locallyResolved reports whether importPath is module or one of its
// subpackages.
func locallyResolved(importPath, module string) bool {
	return importPath == module || strings.HasPrefix(importPath, module+"/")
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintf(os.Stderr, "usage: %s <cap.toml> <mission.dsl>\n", os.Args[0])
		os.Exit(2)
	}
	capPath, dslPath := os.Args[1], os.Args[2]

	unsupported, err := loadCap(capPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	dslFile, err := os.Open(dslPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: opening %s: %v\n", dslPath, err)
		os.Exit(1)
	}
	defer dslFile.Close()

	mission, err := Parse(dslPath, dslFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: parsing %s: %v\n", dslPath, err)
		os.Exit(1)
	}

	var imports []*ImportSpec
	if mission.Import != nil {
		imports = mission.Import.Imports
	}

	// Override paths are resolved relative to the mission file's own
	// directory, so a mission author can point at local sibling checkouts
	// without depending on the compiler's working directory.
	dslDir := filepath.Dir(dslPath)
	var overridePaths []string
	if mission.Override != nil {
		for _, o := range mission.Override.Paths {
			p := o.Path
			if !filepath.IsAbs(p) {
				p = filepath.Join(dslDir, p)
			}
			overridePaths = append(overridePaths, p)
		}
	}

	overridden, err := overriddenModules(overridePaths)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	repoRoot, err := findRepoRoot()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	workspace, cleanup, err := newWorkspace(repoRoot, overridden)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
	// Only cleaned up on a failed compile: on success, workspace holds the
	// generated main.go (and everything it needs to build), left in place
	// for a later "go build" step to turn into the per-device mission
	// binary.
	generated := false
	defer func() {
		if !generated {
			cleanup()
		}
	}()

	if err := installImports(workspace, imports, overridden); err != nil {
		fmt.Fprintf(os.Stderr, "error: installing imports: %v\n", err)
		os.Exit(1)
	}

	overlay, err := scrubPackages(imports, workspace, unsupported)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: scrubbing packages: %v\n", err)
		os.Exit(1)
	}

	registry, err := loadPackages(imports, workspace, overlay)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: loading packages: %v\n", err)
		os.Exit(1)
	}

	ir, err := Link(mission, registry)
	if err != nil {
		fmt.Printf("link failed: %v\n", err)
		os.Exit(1)
	}

	if err := Generate(ir, registry.Alias, workspace); err != nil {
		fmt.Fprintf(os.Stderr, "error: generating mission: %v\n", err)
		os.Exit(1)
	}
	generated = true
	fmt.Printf("generated mission at %s\n", filepath.Join(workspace, "main.go"))
}
