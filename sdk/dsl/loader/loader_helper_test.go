package loader

import (
	"go/ast"
	"go/doc"
	"go/parser"
	"go/token"
	"go/types"
	"sync"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk"
	"golang.org/x/tools/go/packages"
)

// fixturesPkgPath is the import path of the on-disk fixture package
// (testdata/fixtures/fixtures.go) that loader_test.go loads through the
// real LoadTypes/packages.Load path.
const fixturesPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl/loader/testdata/fixtures"

// ambiguousPkgPath is the import path of the on-disk fixture package
// (testdata/ambiguous/ambiguous.go) holding a type that implements more
// than one dsl interface, kept separate from fixturesPkgPath so the
// happy-path loader tests don't also trip the ambiguous-interface error.
const ambiguousPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl/loader/testdata/ambiguous"

// sharedRegistryOnce guards the single LoadTypes call behind
// sharedFixtureRegistry, since LoadTypes type-checks the entire transitive
// dependency graph of dslPkgPath (hundreds of packages) and paying that cost
// once for the whole test binary instead of once per test is the difference
// between a sub-second suite and one that takes several seconds.
var (
	sharedRegistryOnce sync.Once
	sharedRegistryVal  *TypeRegistry
	sharedRegistryErrs []*sdk.CompileError
)

// sharedFixtureRegistry returns the result of loading dslPkgPath and
// fixturesPkgPath (unaliased), running LoadTypes at most once no matter how
// many tests call it. Only use this for tests that want exactly this pair of
// imports with no alias; anything else (a different import set, an alias,
// or a case that expects errors) needs its own LoadTypes call.
func sharedFixtureRegistry(t *testing.T) *TypeRegistry {
	t.Helper()
	sharedRegistryOnce.Do(func() {
		imports := []*PackageRequest{{Path: dslPkgPath}, {Path: fixturesPkgPath}}
		sharedRegistryVal, sharedRegistryErrs = LoadTypes(imports, "", nil)
	})
	if len(sharedRegistryErrs) > 0 {
		t.Fatalf("LoadTypes() errors = %v, want none", sharedRegistryErrs)
	}
	return sharedRegistryVal
}

// typeCheckFixture parses and type-checks src as a standalone package named
// pkgName, returning its *doc.Type map (as packageDocTypes would produce)
// alongside the type-checked *types.Package, so extract_test.go and
// util_test.go can exercise structFields/enumValues/packageDocTypes against
// real go/types and go/doc output without needing a package on disk. src
// must not import anything, since no importer is configured.
func typeCheckFixture(t *testing.T, pkgName, src string) (*types.Package, map[string]*doc.Type) {
	t.Helper()
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, pkgName+".go", src, parser.ParseComments)
	if err != nil {
		t.Fatalf("ParseFile: %v", err)
	}
	conf := types.Config{}
	tpkg, err := conf.Check(pkgName, fset, []*ast.File{file}, nil)
	if err != nil {
		t.Fatalf("types.Config.Check: %v", err)
	}
	docTypes := packageDocTypes(&packages.Package{
		PkgPath: pkgName,
		Fset:    fset,
		Syntax:  []*ast.File{file},
	})
	return tpkg, docTypes
}

// namedStruct looks up name in tpkg's scope and returns its underlying
// *types.Struct, failing the test if name isn't a struct type.
func namedStruct(t *testing.T, tpkg *types.Package, name string) (*types.Named, *types.Struct) {
	t.Helper()
	obj := tpkg.Scope().Lookup(name)
	if obj == nil {
		t.Fatalf("type %q not found in checked package", name)
	}
	named, ok := obj.Type().(*types.Named)
	if !ok {
		t.Fatalf("%q is not a named type", name)
	}
	st, ok := named.Underlying().(*types.Struct)
	if !ok {
		t.Fatalf("%q is not a struct type", name)
	}
	return named, st
}

// fieldByName returns the field in fields named name, failing the test if
// it isn't present.
func fieldByName(t *testing.T, fields []Field, name string) Field {
	t.Helper()
	for _, f := range fields {
		if f.Name == name {
			return f
		}
	}
	t.Fatalf("field %q not found in %v", name, fields)
	return Field{}
}

// keys returns m's keys, for use in test failure messages.
func keys[V any](m map[string]V) []string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	return ks
}
