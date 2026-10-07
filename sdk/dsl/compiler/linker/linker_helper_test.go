package linker

import (
	"strings"
	"sync"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
)

// dslPkgPath is the base DSL package, which LoadTypes requires to be
// loaded so it can find the Action/Event/Datatype interfaces.
const dslPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl"

// fixturesPkgPath is the import path of the on-disk fixture package
// (testdata/fixtures/fixtures.go) the tests link against.
const fixturesPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/linker/testdata/fixtures"

// geoPkgPath is the import path of the on-disk fixture package
// (testdata/geo/geo.go) whose name collides with a template import.
const geoPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/linker/testdata/geo"

// sharedRegistryOnce and aliasedRegistryOnce guard the LoadTypes calls
// behind sharedRegistry and aliasedRegistry, since LoadTypes type-checks
// the entire transitive dependency graph of dslPkgPath and paying that
// cost once per registry instead of once per test keeps the suite fast.
var (
	sharedRegistryOnce sync.Once
	sharedRegistryVal  *loader.TypeRegistry
	sharedRegistryErrs []*sdk.CompileError

	aliasedRegistryOnce sync.Once
	aliasedRegistryVal  *loader.TypeRegistry
	aliasedRegistryErrs []*sdk.CompileError
)

// sharedRegistry returns the result of loading dslPkgPath, fixturesPkgPath
// and geoPkgPath (all unaliased), running LoadTypes at most once no matter
// how many tests call it.
func sharedRegistry(t *testing.T) *loader.TypeRegistry {
	t.Helper()
	sharedRegistryOnce.Do(func() {
		imports := []*loader.PackageRequest{{Path: dslPkgPath}, {Path: fixturesPkgPath}, {Path: geoPkgPath}}
		sharedRegistryVal, sharedRegistryErrs = loader.LoadTypes(imports, "", nil, nil)
	})
	if len(sharedRegistryErrs) > 0 {
		t.Fatalf("LoadTypes() errors = %v, want none", sharedRegistryErrs)
	}
	return sharedRegistryVal
}

// aliasedRegistry returns the result of loading dslPkgPath and
// fixturesPkgPath, with fixturesPkgPath imported under the alias "fx",
// running LoadTypes at most once no matter how many tests call it.
func aliasedRegistry(t *testing.T) *loader.TypeRegistry {
	t.Helper()
	aliasedRegistryOnce.Do(func() {
		imports := []*loader.PackageRequest{{Path: dslPkgPath}, {Path: fixturesPkgPath, Alias: "fx"}}
		aliasedRegistryVal, aliasedRegistryErrs = loader.LoadTypes(imports, "", nil, nil)
	})
	if len(aliasedRegistryErrs) > 0 {
		t.Fatalf("LoadTypes() errors = %v, want none", aliasedRegistryErrs)
	}
	return aliasedRegistryVal
}

// mustParse parses src as a DSL mission file, failing the test on a parse
// error.
func mustParse(t *testing.T, src string) *parser.Ast {
	t.Helper()
	ast, err := parser.Parse("test.dsl", strings.NewReader(src))
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	return ast
}

// mission returns a complete mission source importing fixturesPkgPath,
// with data and actions spliced into their stanzas. It always declares a
// fixtures.Hover action named hover (which it starts in) and a
// fixtures.Seen event named seen, since Link requires every stanza.
// Each of data and actions should be zero or more newline-terminated
// declaration lines.
func mission(data, actions string) string {
	return "Import:\n" +
		"    \"" + fixturesPkgPath + "\"\n" +
		"Data:\n" + data +
		"Actions:\n" +
		"    fixtures.Hover hover()\n" + actions +
		"Events:\n" +
		"    fixtures.Seen seen()\n" +
		"Mission:\n" +
		"Start hover\n"
}

// mustLink parses and links src against sharedRegistry, failing the test
// if linking reports any errors.
func mustLink(t *testing.T, src string) *IR {
	t.Helper()
	ir, errs := Link(mustParse(t, src), sharedRegistry(t))
	if len(errs) > 0 {
		t.Fatalf("Link() errors = %v, want none", errs)
	}
	if ir == nil {
		t.Fatalf("Link() = nil IR with no errors")
	}
	return ir
}

// mustFailLink parses and links src against sharedRegistry, failing the
// test unless linking reports at least one error and returns a nil IR.
func mustFailLink(t *testing.T, src string) []*sdk.CompileError {
	t.Helper()
	ir, errs := Link(mustParse(t, src), sharedRegistry(t))
	if len(errs) == 0 {
		t.Fatalf("Link() errors = none, want at least one")
	}
	if ir != nil {
		t.Errorf("Link() IR = %+v, want nil when there are errors", ir)
	}
	return errs
}

// findError returns the first error whose message contains substr,
// failing the test if there is none.
func findError(t *testing.T, errs []*sdk.CompileError, substr string) *sdk.CompileError {
	t.Helper()
	for _, e := range errs {
		if strings.Contains(e.Error(), substr) {
			return e
		}
	}
	t.Fatalf("errors = %v, want one containing %q", errs, substr)
	return nil
}

// mustDecl returns the linked declaration named name, failing the test if
// it isn't present.
func mustDecl(t *testing.T, ir *IR, name string) *TypeIR {
	t.Helper()
	decl, ok := ir.All[name]
	if !ok {
		t.Fatalf("declaration %q not linked", name)
	}
	return decl
}

// parseDecl parses line as the only declaration of an Actions stanza,
// returning it so render tests can feed its attributes to renderType.
func parseDecl(t *testing.T, line string) *parser.Decl {
	t.Helper()
	ast := mustParse(t, "Actions:\n    "+line+"\n")
	if ast.Actions == nil || len(ast.Actions.Decls) != 1 {
		t.Fatalf("Actions = %+v, want exactly one declaration", ast.Actions)
	}
	return ast.Actions.Decls[0]
}

// mustField returns the field of the registry type typeName named name,
// searching both required and optional fields, failing the test if it
// isn't present.
func mustField(t *testing.T, registry *loader.TypeRegistry, typeName, name string) loader.Field {
	t.Helper()
	base, ok := registry.All[typeName]
	if !ok {
		t.Fatalf("type %q not registered", typeName)
	}
	for _, f := range append(append([]loader.Field{}, base.Fields...), base.OptFields...) {
		if f.Name == name {
			return f
		}
	}
	t.Fatalf("field %q not found on %s", name, typeName)
	return loader.Field{}
}
