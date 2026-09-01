// Command compiler compiles a DSL mission file against a vehicle
// capability manifest into a standalone mission binary: it scrubs
// unsupported types out of the SDK per the cap file, links the mission's
// Data/Actions/Events declarations against what's left, and builds the
// result.
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
	"github.com/cmusatyalab/steeleagle/sdk/geo"
)

func main() {
	dslPath := flag.String("dsl", "", "path to the mission DSL file (required)")
	capPath := flag.String("cap", "", "path to the vehicle's cap.toml manifest (optional; an empty manifest is used if omitted)")
	geoJSONPath := flag.String("geojson", "", "path to a GeoJSON map for the mission (optional)")
	arch := flag.String("arch", "", "GOARCH to cross-compile the mission binary for (optional; defaults to the host architecture)")
	out := flag.String("out", "mission", "name of the compiled mission binary")
	steeleagleRef := flag.String("steeleagle-ref", "", "git branch, tag, or commit to pull every github.com/cmusatyalab/steeleagle package (base SDK and any mission import under that module) against; overrides any per-import version in the DSL file's Import stanza for those packages (optional; defaults to each import's own declared version, or \"latest\" on the module's default branch)")
	flag.Parse()

	if *dslPath == "" {
		fmt.Fprintln(os.Stderr, "error: -dsl is required")
		flag.Usage()
		os.Exit(2)
	}

	capBytes, err := readFileOrEmpty(*capPath)
	if err != nil {
		fatalf("reading cap file: %v", err)
	}
	capFile, err := sdk.ParseCapFromBytes(capBytes)
	if err != nil {
		fatalf("parsing cap file: %v", err)
	}

	var geoJSONBytes []byte
	sdkTypes := map[string][]string{}
	if *geoJSONPath != "" {
		geoJSONBytes, err = os.ReadFile(*geoJSONPath)
		if err != nil {
			fatalf("reading GeoJSON: %v", err)
		}
		names, err := geo.NewMap().GetFeatureNamesFromGeoJson(geoJSONBytes)
		if err != nil {
			fatalf("parsing GeoJSON: %v", err)
		}
		sdkTypes["MapFeature"] = names
	}

	dslFile, err := os.Open(*dslPath)
	if err != nil {
		fatalf("opening %s: %v", *dslPath, err)
	}
	mission, err := parser.Parse(*dslPath, dslFile)
	dslFile.Close()
	if err != nil {
		fatalf("parsing %s: %v", *dslPath, err)
	}

	var imports []*parser.ImportSpec
	if mission.Import != nil {
		imports = mission.Import.Imports
	}
	imports = compiler.EnsureBaseImports(imports)

	var overridePaths []string
	if mission.Override != nil {
		for _, o := range mission.Override.Paths {
			overridePaths = append(overridePaths, o.Path)
		}
	}

	var resolvedRef string
	if *steeleagleRef != "" {
		resolvedRef, err = compiler.ResolveSteeleagleRef(*steeleagleRef)
		if err != nil {
			fatalf("resolving -steeleagle-ref %s: %v", *steeleagleRef, err)
		}
	}

	workspace, cleanup, err := compiler.NewWorkspace(imports, resolvedRef, overridePaths)
	if err != nil {
		fatalf("setting up build workspace: %v", err)
	}
	defer cleanup()

	pkgPaths := make([]string, len(imports))
	for i, imp := range imports {
		pkgPaths[i] = imp.Path
	}

	rawPkgs, err := compiler.LoadSteeleaglePackages(workspace, pkgPaths)
	if err != nil {
		fatalf("loading SDK packages: %v", err)
	}
	overlay, compileErrs := sdk.CreateOverlay(capFile, sdkTypes, nil, rawPkgs)
	if len(compileErrs) > 0 {
		fatalCompileErrors("scrubbing SDK packages", compileErrs)
	}

	requests := make([]*loader.PackageRequest, len(imports))
	for i, imp := range imports {
		requests[i] = &loader.PackageRequest{Path: imp.Path, Alias: imp.Alias}
	}
	// buildEnv mirrors what tidyAndBuild ultimately builds the mission
	// binary with, so this type-checking pass's build-cache entries are
	// reusable by the final "go build" instead of being computed twice
	// under two different CGO_ENABLED/GOARCH cache keys.
	buildEnv := []string{"CGO_ENABLED=0"}
	if *arch != "" {
		buildEnv = append(buildEnv, "GOARCH="+*arch)
	}
	registry, compileErrs := loader.LoadTypes(requests, workspace, overlay, buildEnv)
	if len(compileErrs) > 0 {
		fatalCompileErrors("loading DSL types", compileErrs)
	}

	ir, err := compiler.BuildIR(mission, registry)
	if err != nil {
		fatalf("linking mission: %v", err)
	}

	if err := compiler.Generate(ir, capBytes, geoJSONBytes, workspace); err != nil {
		fatalf("generating mission: %v", err)
	}

	overlayPath, err := compiler.MaterializeOverlay(workspace, overlay)
	if err != nil {
		fatalf("materializing overlay: %v", err)
	}

	outPath, err := compiler.AbsOutPath(*out)
	if err != nil {
		fatalf("resolving output path: %v", err)
	}
	if err := compiler.TidyAndBuild(workspace, overlayPath, outPath, *arch); err != nil {
		fatalf("building mission: %v", err)
	}

	fmt.Printf("compiled mission to %s\n", outPath)
}

// readFileOrEmpty reads path, returning an empty slice (rather than an
// error) when path is empty -- the caller then parses that into an empty
// CapFile, whose Supports check always reports true (nothing unsupported).
func readFileOrEmpty(path string) ([]byte, error) {
	if path == "" {
		return nil, nil
	}
	return os.ReadFile(path)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "error: "+format+"\n", args...)
	os.Exit(1)
}

func fatalCompileErrors(stage string, errs []*sdk.CompileError) {
	fmt.Fprintf(os.Stderr, "error: %s:\n", stage)
	for _, e := range errs {
		if e.File != "" {
			loc := e.File
			if e.LineNo > 0 {
				loc = fmt.Sprintf("%s:%d", loc, e.LineNo)
			}
			fmt.Fprintf(os.Stderr, "  %s: %v\n", loc, e.Err)
			continue
		}
		fmt.Fprintf(os.Stderr, "  %v\n", e.Err)
	}
	os.Exit(1)
}
