// Command compiler compiles a DSL mission file against a vehicle capability
// manifest: it scrubs unsupported types out of the SDK before loading it, then
// links the mission against what's left.
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/BurntSushi/toml"
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

// newWorkspace creates a scratch directory containing a throwaway go.mod
// (to hold requires for whatever mission-specific packages get installed
// into it) and a go.work that also "uses" repoRoot, so the base SDK
// packages resolve against the real local source. The returned cleanup
// removes the directory and must be called once the workspace is no longer
// needed.
func newWorkspace(repoRoot string) (dir string, cleanup func(), err error) {
	dir, err = os.MkdirTemp("", "steeleagle-dsl-*")
	if err != nil {
		return "", nil, fmt.Errorf("creating workspace: %w", err)
	}
	cleanup = func() { os.RemoveAll(dir) }

	goVersion := strings.TrimPrefix(runtime.Version(), "go")

	goMod := fmt.Sprintf("module steeleagle-dsl-workspace\n\ngo %s\n", goVersion)
	if err := os.WriteFile(filepath.Join(dir, "go.mod"), []byte(goMod), 0644); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("writing go.mod: %w", err)
	}

	goWork := fmt.Sprintf("go %s\n\nuse (\n\t%s\n\t.\n)\n", goVersion, repoRoot)
	if err := os.WriteFile(filepath.Join(dir, "go.work"), []byte(goWork), 0644); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("writing go.work: %w", err)
	}

	return dir, cleanup, nil
}

// installImports fetches every import that isn't already part of
// steeleagleModule (those resolve locally through the workspace's "use" of
// repoRoot) into workspace's go.mod, so loadPackages/scrubPackages can find
// them afterwards.
func installImports(workspace string, imports []*ImportSpec) error {
	env := append(os.Environ(), "GOWORK="+filepath.Join(workspace, "go.work"))
	for _, imp := range imports {
		if imp.Path == steeleagleModule || strings.HasPrefix(imp.Path, steeleagleModule+"/") {
			continue
		}
		cmd := exec.Command("go", "get", imp.Path)
		cmd.Dir = workspace
		cmd.Env = env
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("go get %s: %w\n%s", imp.Path, err, out)
		}
	}
	return nil
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

	repoRoot, err := findRepoRoot()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	workspace, cleanup, err := newWorkspace(repoRoot)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
	defer cleanup()

	if err := installImports(workspace, imports); err != nil {
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

	if _, err := Link(mission, registry); err != nil {
		fmt.Printf("link failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("link succeeded")
}
