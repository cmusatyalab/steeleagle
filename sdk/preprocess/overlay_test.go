package preprocess

import (
	"encoding/json"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"golang.org/x/tools/go/packages"
)

// Import paths the tests load or name packages by.
const (
	sdkModPath    = "github.com/cmusatyalab/steeleagle/sdk"
	sdkPkgPath    = "github.com/cmusatyalab/steeleagle/sdk"
	paramsPkgPath = "github.com/cmusatyalab/steeleagle/sdk/params"
	otherPkgPath  = "example.com/consts/other"
)

// writeConstPkg writes files (name -> source) into a temporary directory
// and returns them as a loaded package at pkgPath.
func writeConstPkg(t *testing.T, pkgPath string, files map[string]string) *packages.Package {
	t.Helper()
	dir := t.TempDir()
	pkg := &packages.Package{PkgPath: pkgPath}
	for name, src := range files {
		path := filepath.Join(dir, name)
		if err := os.WriteFile(path, []byte(src), 0o644); err != nil {
			t.Fatal(err)
		}
		pkg.GoFiles = append(pkg.GoFiles, path)
	}
	return pkg
}

// TestOverlayPackagesGeneratesConstsFromLoadedSource checks that constants
// are generated into the const packages' own files on disk, each type's
// constants landing in the file that declares it, rather than into a copy
// of the source embedded in the compiler.
func TestOverlayPackagesGeneratesConstsFromLoadedSource(t *testing.T) {
	params := writeConstPkg(t, paramsPkgPath, map[string]string{
		"params.go": "package params\n\ntype Polygon string\n\n// OnlyInLoadedVersion marks this as the loaded source.\ntype OnlyInLoadedVersion int\n",
		"extra.go":  "package params\n\ntype Point string\n",
		"other.go":  "package params\n\ntype Unrelated int\n",
	})
	other := writeConstPkg(t, otherPkgPath, map[string]string{
		"other.go": "package other\n\ntype Role string\n",
	})
	consts := map[string]map[string][]string{
		paramsPkgPath: {"Polygon": {"area"}, "Point": {"home"}},
		otherPkgPath:  {"Role": {"Leader"}},
	}

	overlay, errs := overlayPackages(func(string) bool { return true }, consts, []*packages.Package{params, other})
	if len(errs) > 0 {
		t.Fatalf("overlayPackages() errors = %v", errs)
	}

	// file -> substrings its overlay must contain
	checks := map[string][]string{}
	for _, file := range params.GoFiles {
		switch filepath.Base(file) {
		case "params.go":
			checks[file] = []string{"OnlyInLoadedVersion", `Polygon_area Polygon = "area"`}
		case "extra.go":
			checks[file] = []string{`Point_home Point = "home"`}
		case "other.go":
			if _, ok := overlay[file]; ok {
				t.Errorf("overlay has %s, which declares no const types", file)
			}
		}
	}
	checks[other.GoFiles[0]] = []string{`Role_Leader Role = "Leader"`}
	for file, wants := range checks {
		got, ok := overlay[file]
		if !ok {
			t.Errorf("overlay missing %s", file)
			continue
		}
		for _, want := range wants {
			if !strings.Contains(string(got), want) {
				t.Errorf("overlay[%s] = %s, want it to contain %q", filepath.Base(file), got, want)
			}
		}
	}
}

// TestOverlayPackagesUndeclaredConstType checks that a const type which no
// file of the package declares is reported as an error.
func TestOverlayPackagesUndeclaredConstType(t *testing.T) {
	params := writeConstPkg(t, paramsPkgPath, map[string]string{
		"params.go": "package params\n\ntype Polygon string\n",
	})
	consts := map[string]map[string][]string{paramsPkgPath: {"Polygon": {"area"}, "Missing": {"x"}}}

	_, errs := overlayPackages(func(string) bool { return true }, consts, []*packages.Package{params})
	if len(errs) != 1 || !strings.Contains(errs[0].Error(), `"Missing"`) {
		t.Fatalf("overlayPackages() errors = %v, want one error naming Missing", errs)
	}
	if errs[0].File != paramsPkgPath {
		t.Errorf("error File = %q, want %q", errs[0].File, paramsPkgPath)
	}
}

// pkgPaths returns the import paths of pkgs, sorted.
func pkgPaths(pkgs []*packages.Package) []string {
	paths := []string{}
	for _, p := range pkgs {
		paths = append(paths, p.PkgPath)
	}
	slices.Sort(paths)
	return paths
}

// TestModulePackagesFiltersByModule checks that ModulePackages keeps the
// packages of listed modules and of the SDK's module, wherever they sit in
// the import graph, and drops unlisted modules and the standard library.
func TestModulePackagesFiltersByModule(t *testing.T) {
	sdkMod := &packages.Module{Path: "example.com/steeleagle"}
	listedMod := &packages.Module{Path: "example.com/listed"}
	externalMod := &packages.Module{Path: "example.com/external"}

	fmtPkg := &packages.Package{PkgPath: "fmt"}
	params := &packages.Package{PkgPath: "github.com/cmusatyalab/steeleagle/sdk/params", Module: sdkMod}
	sdkPkg := &packages.Package{
		PkgPath: sdkPkgPath,
		Module:  sdkMod,
		Imports: map[string]*packages.Package{"fmt": fmtPkg, params.PkgPath: params},
	}
	// A listed package reached only through an unlisted one is still kept
	listedDeep := &packages.Package{PkgPath: "example.com/listed/deep", Module: listedMod}
	external := &packages.Package{
		PkgPath: "example.com/external/lib",
		Module:  externalMod,
		Imports: map[string]*packages.Package{listedDeep.PkgPath: listedDeep},
	}
	listed := &packages.Package{
		PkgPath: "example.com/listed/actions",
		Module:  listedMod,
		Imports: map[string]*packages.Package{sdkPkgPath: sdkPkg, external.PkgPath: external},
	}

	got := pkgPaths(ModulePackages([]*packages.Package{listed}, []string{"example.com/listed"}, []string{sdkPkgPath}))
	want := []string{
		"example.com/listed/actions",
		"example.com/listed/deep",
		sdkPkgPath,
		"github.com/cmusatyalab/steeleagle/sdk/params",
	}
	if !slices.Equal(got, want) {
		t.Errorf("ModulePackages() = %v, want %v", got, want)
	}
}

// TestModulePackagesNoModulesKeepsSdk checks that the SDK's module is kept
// even when no modules are listed.
func TestModulePackagesNoModulesKeepsSdk(t *testing.T) {
	sdkMod := &packages.Module{Path: "example.com/steeleagle"}
	sdkPkg := &packages.Package{PkgPath: sdkPkgPath, Module: sdkMod}
	other := &packages.Package{
		PkgPath: "example.com/other",
		Module:  &packages.Module{Path: "example.com/other"},
		Imports: map[string]*packages.Package{sdkPkgPath: sdkPkg},
	}

	got := pkgPaths(ModulePackages([]*packages.Package{other}, nil, []string{sdkPkgPath}))
	if want := []string{sdkPkgPath}; !slices.Equal(got, want) {
		t.Errorf("ModulePackages() = %v, want %v", got, want)
	}
}

// actionsPkgPath is an SDK package whose import graph reaches the SDK's
// root package and external modules such as grpc.
const actionsPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"

// TestModulePackagesRealGraph loads an SDK package's full import graph
// and checks that only the SDK's module is kept by default, and that
// listing an external module adds its packages.
func TestModulePackagesRealGraph(t *testing.T) {
	cfg := &packages.Config{
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedImports | packages.NeedDeps | packages.NeedModule,
	}
	roots, err := packages.Load(cfg, actionsPkgPath)
	if err != nil {
		t.Fatalf("packages.Load() error = %v", err)
	}

	got := ModulePackages(roots, nil, []string{sdkPkgPath})
	paths := pkgPaths(got)
	for _, p := range got {
		if p.Module == nil || p.Module.Path != sdkModPath {
			t.Errorf("package %s from module %v kept, want only the SDK's module", p.PkgPath, p.Module)
		}
	}
	for _, want := range []string{actionsPkgPath, sdkPkgPath, paramsPkgPath} {
		if !slices.Contains(paths, want) {
			t.Errorf("ModulePackages() missing %s", want)
		}
	}

	withGrpc := pkgPaths(ModulePackages(roots, []string{"google.golang.org/grpc"}, []string{sdkPkgPath}))
	if !slices.Contains(withGrpc, "google.golang.org/grpc") {
		t.Errorf("ModulePackages() with grpc listed is missing google.golang.org/grpc")
	}
}

// TestModulePackagesSdkSubpackage checks that the SDK's module is kept
// when the graph only reaches an SDK subpackage, not the SDK's root
// package.
func TestModulePackagesSdkSubpackage(t *testing.T) {
	sdkMod := &packages.Module{Path: "example.com/steeleagle"}
	params := &packages.Package{PkgPath: sdkPkgPath + "/params", Module: sdkMod}
	// A package whose path only shares the SDK's as a string prefix isn't
	// an SDK package
	lookalike := &packages.Package{
		PkgPath: sdkPkgPath + "extra",
		Module:  &packages.Module{Path: "example.com/lookalike"},
	}
	main := &packages.Package{
		PkgPath: "example.com/main",
		Module:  &packages.Module{Path: "example.com/main"},
		Imports: map[string]*packages.Package{params.PkgPath: params, lookalike.PkgPath: lookalike},
	}

	got := pkgPaths(ModulePackages([]*packages.Package{main}, nil, []string{sdkPkgPath}))
	if want := []string{params.PkgPath}; !slices.Equal(got, want) {
		t.Errorf("ModulePackages() = %v, want %v", got, want)
	}
}

// TestWriteOverlay checks that WriteOverlay writes each replacement and a
// JSON file mapping the replaced files to them, clearing out anything
// already in the directory.
func TestWriteOverlay(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "overlay")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	stale := filepath.Join(dir, "stale.go")
	if err := os.WriteFile(stale, nil, 0o644); err != nil {
		t.Fatal(err)
	}
	overlay := map[string][]byte{"/src/a/x.go": []byte("package a"), "/src/b/x.go": []byte("package b")}
	path, err := WriteOverlay(dir, overlay)
	if err != nil {
		t.Fatalf("WriteOverlay() error = %v", err)
	}
	if _, err := os.Stat(stale); !os.IsNotExist(err) {
		t.Errorf("stale file left in the overlay directory: %v", err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var parsed struct{ Replace map[string]string }
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatal(err)
	}
	if len(parsed.Replace) != len(overlay) {
		t.Fatalf("Replace = %v, want an entry per overlay file", parsed.Replace)
	}
	for file, want := range overlay {
		got, err := os.ReadFile(parsed.Replace[file])
		if err != nil {
			t.Errorf("replacement for %s: %v", file, err)
			continue
		}
		if string(got) != string(want) {
			t.Errorf("replacement for %s = %q, want %q", file, got, want)
		}
	}
}

// TestModulePackagesWithoutModulesOf checks that without modulesOf only
// the listed modules are kept.
func TestModulePackagesWithoutModulesOf(t *testing.T) {
	sdkPkg := &packages.Package{PkgPath: sdkPkgPath, Module: &packages.Module{Path: "example.com/steeleagle"}}
	listed := &packages.Package{
		PkgPath: "example.com/listed",
		Module:  &packages.Module{Path: "example.com/listed"},
		Imports: map[string]*packages.Package{sdkPkgPath: sdkPkg},
	}
	got := pkgPaths(ModulePackages([]*packages.Package{listed}, []string{"example.com/listed"}, nil))
	if want := []string{"example.com/listed"}; !slices.Equal(got, want) {
		t.Errorf("ModulePackages() = %v, want %v", got, want)
	}
}
