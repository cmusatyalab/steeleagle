package loader

import (
	"go/types"
	"testing"
)

// TestLoaderRegistersByInterface checks that LoadTypes sorts each
// exported struct in the imported packages into Actions, Events, or
// Datatypes according to which of the three dsl interfaces it implements,
// qualifying each name with its package's own name, and that a struct
// implementing none of them (Plain) is skipped entirely.
func TestLoaderRegistersByInterface(t *testing.T) {
	reg := sharedFixtureRegistry(t)

	if _, ok := reg.Actions["fixtures.Hover"]; !ok {
		t.Errorf("Actions = %v, want fixtures.Hover registered", keys(reg.Actions))
	}
	if _, ok := reg.Events["fixtures.Seen"]; !ok {
		t.Errorf("Events = %v, want fixtures.Seen registered", keys(reg.Events))
	}
	if _, ok := reg.Datatypes["fixtures.Waypoint"]; !ok {
		t.Errorf("Datatypes = %v, want fixtures.Waypoint registered", keys(reg.Datatypes))
	}
	for _, m := range []map[string]*Base{reg.Actions, reg.Events, reg.Datatypes} {
		if _, ok := m["fixtures.Plain"]; ok {
			t.Errorf("fixtures.Plain implements no dsl interface, but was registered in %v", keys(m))
		}
	}
}

// TestLoaderExtractsFieldsAndOptionalTag checks that the Action
// registered for fixtures.Hover carries its required/optional field split
// and doc comments through end to end, from source comment to the
// TypeRegistry.
func TestLoaderExtractsFieldsAndOptionalTag(t *testing.T) {
	reg := sharedFixtureRegistry(t)

	hover, ok := reg.Actions["fixtures.Hover"]
	if !ok {
		t.Fatalf("fixtures.Hover not registered as an Action")
	}
	if len(hover.Fields) != 1 || hover.Fields[0].Name != "Duration" {
		t.Fatalf("Fields = %v, want exactly [Duration]", hover.Fields)
	}
	if want := "Duration is how long to hover, in seconds."; hover.Fields[0].Comment != want {
		t.Errorf("Duration.Comment = %q, want %q", hover.Fields[0].Comment, want)
	}
	if len(hover.OptFields) != 1 || hover.OptFields[0].Name != "Altitude" {
		t.Fatalf("OptFields = %v, want exactly [Altitude]", hover.OptFields)
	}
	if want := "meters above ground"; hover.OptFields[0].Comment != want {
		t.Errorf("Altitude.Comment = %q, want %q", hover.OptFields[0].Comment, want)
	}
}

// TestLoaderExtractsEnumValues checks that a uint32-backed named type
// (fixtures.Mode) is registered under Enums with one field per exported
// constant of that type, including its doc/line comment.
func TestLoaderExtractsEnumValues(t *testing.T) {
	reg := sharedFixtureRegistry(t)

	mode, ok := reg.Enums["fixtures.Mode"]
	if !ok {
		t.Fatalf("fixtures.Mode not registered as an Enum")
	}
	idle := fieldByName(t, mode.Fields, "ModeIdle")
	if want := "ModeIdle is the default, do-nothing mode."; idle.Comment != want {
		t.Errorf("ModeIdle.Comment = %q, want %q", idle.Comment, want)
	}
	active := fieldByName(t, mode.Fields, "ModeActive")
	if want := "mode entered once a mission starts moving"; active.Comment != want {
		t.Errorf("ModeActive.Comment = %q, want %q", active.Comment, want)
	}
}

// TestLoaderAmbiguousInterfaceReportsError checks that a struct
// implementing more than one of Action/Event/Datatype (fixtures.Ambiguous)
// produces a *sdk.CompileError instead of being silently registered under
// either interface.
func TestLoaderAmbiguousInterfaceReportsError(t *testing.T) {
	imports := []*PackageRequest{
		{Path: dslPkgPath},
		{Path: ambiguousPkgPath},
	}
	reg, errs := LoadTypes(imports, "", nil)
	if len(errs) != 1 {
		t.Fatalf("LoadTypes() errors = %v, want exactly 1 (ambiguous.Ambiguous)", errs)
	}
	if reg != nil {
		t.Errorf("registry = %v, want nil once any compile error is returned", reg)
	}
}

// TestLoaderMissingDslImportErrors checks that omitting dslPkgPath from
// the requested imports fails with a compile error naming the missing
// package, instead of proceeding without the Action/Event/Datatype
// interfaces to check against.
func TestLoaderMissingDslImportErrors(t *testing.T) {
	imports := []*PackageRequest{{Path: fixturesPkgPath}}
	reg, errs := LoadTypes(imports, "", nil)
	if reg != nil {
		t.Errorf("registry = %v, want nil", reg)
	}
	if len(errs) != 1 {
		t.Fatalf("errors = %v, want exactly 1", errs)
	}
}

// TestLoaderUnknownImportPathErrors checks that requesting an import
// path that doesn't exist surfaces as a compile error rather than a Go
// panic or a silently empty registry.
func TestLoaderUnknownImportPathErrors(t *testing.T) {
	imports := []*PackageRequest{
		{Path: dslPkgPath},
		{Path: "github.com/cmusatyalab/steeleagle/sdk/dsl/loader/testdata/does-not-exist"},
	}
	reg, errs := LoadTypes(imports, "", nil)
	if reg != nil {
		t.Errorf("registry = %v, want nil", reg)
	}
	if len(errs) == 0 {
		t.Fatal("errors = none, want at least 1 for the unresolvable import")
	}
}

// TestLoaderQualifiesNamesByAlias checks that when a PackageRequest
// carries an Alias, registered type names are qualified with that alias
// instead of the package's own declared name.
func TestLoaderQualifiesNamesByAlias(t *testing.T) {
	imports := []*PackageRequest{
		{Path: dslPkgPath},
		{Path: fixturesPkgPath, Alias: "fx"},
	}
	reg, errs := LoadTypes(imports, "", nil)
	if len(errs) > 0 {
		t.Fatalf("LoadTypes() errors = %v, want none", errs)
	}
	if _, ok := reg.Events["fx.Seen"]; !ok {
		t.Errorf("Events = %v, want fx.Seen registered under its alias", keys(reg.Events))
	}
	if _, ok := reg.Events["fixtures.Seen"]; ok {
		t.Errorf("Events = %v, want no entry under the unaliased name", keys(reg.Events))
	}
}

// TestLoaderMissingInterfaceErrors checks that lookupInterfaces
// reports an error naming the missing interface instead of returning a
// short slice.
func TestLoaderMissingInterfaceErrors(t *testing.T) {
	reg := sharedFixtureRegistry(t)
	dslPkg := reg.Packages[dslPkgPath]

	if _, err := lookupInterfaces(dslPkg, []string{"Action", "NotReal"}); err == nil {
		t.Fatal("lookupInterfaces() error = nil, want an error for the missing interface")
	}
}

// TestLoaderNonInterfaceTypeErrors checks that naming an
// exported type that isn't itself an interface (dsl.MissionData, a struct)
// reports an error rather than a type assertion panic.
func TestLoaderNonInterfaceTypeErrors(t *testing.T) {
	reg := sharedFixtureRegistry(t)
	dslPkg := reg.Packages[dslPkgPath]

	if _, err := lookupInterfaces(dslPkg, []string{"MissionData"}); err == nil {
		t.Fatal("lookupInterfaces() error = nil, want an error since MissionData is a struct")
	}
}

// TestLoaderImplementsReportsNoMatch checks that a type implementing none of the
// given interfaces returns -1 with no error.
func TestLoaderImplementsReportsNoMatch(t *testing.T) {
	src := `package fixture

type Speaker interface {
	Speak() string
}

type Plain struct{}
`
	tpkg, _ := typeCheckFixture(t, "fixture", src)
	named, _ := namedStruct(t, tpkg, "Plain")
	speaker := tpkg.Scope().Lookup("Speaker").Type().Underlying().(*types.Interface)

	idx, err := implements(named, []*types.Interface{speaker})
	if err != nil {
		t.Fatalf("implements() error = %v, want nil", err)
	}
	if idx != -1 {
		t.Errorf("idx = %d, want -1", idx)
	}
}

// TestLoaderImplementsNilInputsReportNoMatch checks that implements tolerates a
// nil named type or a nil interface slice instead of panicking.
func TestLoaderImplementsNilInputsReportNoMatch(t *testing.T) {
	if idx, err := implements(nil, nil); idx != -1 || err != nil {
		t.Errorf("implements(nil, nil) = (%d, %v), want (-1, nil)", idx, err)
	}
}
