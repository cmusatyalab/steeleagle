package linker

import (
	"go/format"
	"go/types"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
)

// formatDecl gofmts src as the body of a Go file, so tests can compare
// rendered code against expected code without depending on the exact
// whitespace renderType emits.
func formatDecl(t *testing.T, src string) string {
	t.Helper()
	out, err := format.Source([]byte("package p\n\n" + src + "\n"))
	if err != nil {
		t.Fatalf("format.Source(%q) error = %v", src, err)
	}
	return string(out)
}

// valueOf parses src as a single DSL value.
func valueOf(t *testing.T, src string) *parser.Value {
	t.Helper()
	return parseDecl(t, "x.X x(V="+src+")").Attrs[0].Value
}

// TestVarName checks that every declaration's Go identifier is prefixed,
// so that DSL names which are Go keywords or collide with generated code
// still produce valid, unshadowed identifiers.
func TestVarName(t *testing.T) {
	cases := map[string]string{
		"takeoff": "decl_takeoff",
		"func":    "decl_func",
		"data":    "decl_data",
	}
	for name, want := range cases {
		if got := varName(name); got != want {
			t.Errorf("varName(%q) = %q, want %q", name, got, want)
		}
	}
}

// TestRenderImport checks that an import spec is only aliased when an
// alias is given.
func TestRenderImport(t *testing.T) {
	if got, want := renderImport("", "example.com/pkg"), `"example.com/pkg"`; got != want {
		t.Errorf("renderImport(\"\", ...) = %s, want %s", got, want)
	}
	if got, want := renderImport("p", "example.com/pkg"), `p "example.com/pkg"`; got != want {
		t.Errorf("renderImport(\"p\", ...) = %s, want %s", got, want)
	}
}

// TestRenderTypeDeclarationAndLiteral checks that renderType renders a
// prefixed variable declaration when given a name and a bare composite
// literal otherwise.
func TestRenderTypeDeclarationAndLiteral(t *testing.T) {
	reg := sharedRegistry(t)
	if got, want := renderType("h", "fixtures.Hover", nil, reg), "var decl_h = fixtures.Hover{}"; got != want {
		t.Errorf("renderType(\"h\", ...) = %s, want %s", got, want)
	}
	if got, want := renderType("", "fixtures.Hover", nil, reg), "fixtures.Hover{}"; got != want {
		t.Errorf("renderType(\"\", ...) = %s, want %s", got, want)
	}
}

// TestRenderTypeFillsDefaults checks that unset optional fields are only
// rendered when they declare a default, and that each default is rendered
// according to its field's type: a numeric conversion, an enum constant,
// or a quoted string conversion.
func TestRenderTypeFillsDefaults(t *testing.T) {
	decl := parseDecl(t, "fixtures.Fly f(Speed=1.0)")
	got := renderType("f", "fixtures.Fly", decl.Attrs, sharedRegistry(t))
	want := `var decl_f = fixtures.Fly{
	Speed:    float32(1),
	Timeout:  float32(3.0),
	Fallback: fixtures.ModeActive,
	Tag:      fixtures.Label("home"),
}`
	if formatDecl(t, got) != formatDecl(t, want) {
		t.Errorf("renderType() =\n%s\nwant\n%s", got, want)
	}
}

// TestRenderTypeSetFieldOverridesDefault checks that an optional field
// which is set is rendered with its set value instead of its default.
func TestRenderTypeSetFieldOverridesDefault(t *testing.T) {
	decl := parseDecl(t, "fixtures.Fly f(Speed=1.0, Timeout=9.0, Fallback=Idle, Tag=Away)")
	got := renderType("f", "fixtures.Fly", decl.Attrs, sharedRegistry(t))
	want := `var decl_f = fixtures.Fly{
	Speed:    float32(1),
	Timeout:  float32(9),
	Fallback: fixtures.ModeIdle,
	Tag:      fixtures.LabelAway,
}`
	if formatDecl(t, got) != formatDecl(t, want) {
		t.Errorf("renderType() =\n%s\nwant\n%s", got, want)
	}
}

// TestRenderTypeUsesGoTypeName checks that the rendered type name comes
// from the Go type through the generated-code qualifier, so it matches the
// package's import even when the mission imports it under an alias.
func TestRenderTypeUsesGoTypeName(t *testing.T) {
	if got, want := renderType("h", "fx.Hover", nil, aliasedRegistry(t)), "var decl_h = fx.Hover{}"; got != want {
		t.Errorf("renderType() = %s, want %s", got, want)
	}
}

// TestRenderTypeUnknownTypeFallsBack checks that a type missing from the
// registry is rendered by its DSL name with no fields, rather than
// panicking; the linker reports it as an error before rendering matters.
func TestRenderTypeUnknownTypeFallsBack(t *testing.T) {
	if got, want := renderType("", "nope.Thing", nil, sharedRegistry(t)), "nope.Thing{}"; got != want {
		t.Errorf("renderType() = %s, want %s", got, want)
	}
}

// TestRenderValueLiterals checks that each kind of single-line DSL value
// is rendered as the matching Go expression for its field's type.
func TestRenderValueLiterals(t *testing.T) {
	reg := sharedRegistry(t)
	cases := []struct {
		field, value, want string
	}{
		{"Speed", "2.5", "float32(2.5)"},
		{"Speed", "2", "float32(2)"},
		{"Count", "-3", "int32(-3)"},
		{"Note", `"hi"`, `string("hi")`},
		{"Note", `'say "hi"'`, `string("say \"hi\"")`},
		{"Enabled", "true", "true"},
		{"Points", "[1, 2.5]", "[]float64{float64(1), float64(2.5)}"},
		{"Points", "[]", "[]float64{}"},
		{"Mode", "Active", "fixtures.ModeActive"},
		{"Mode", "ModeActive", "fixtures.ModeActive"},
		{"Mode", "fixtures.ModeActive", "fixtures.ModeActive"},
		{"Tag", "Away", "fixtures.LabelAway"},
		{"Tag", `"custom"`, `fixtures.Label("custom")`},
		{"Target", "home", "&decl_home"},
		{"Route", "r", "decl_r"},
	}
	for _, c := range cases {
		field := mustField(t, reg, "fixtures.Fly", c.field)
		if got := renderValue(field.Type, valueOf(t, c.value), reg); got != c.want {
			t.Errorf("renderValue(%s, %s) = %s, want %s", c.field, c.value, got, c.want)
		}
	}
}

// TestRenderValueInlineCtorPointer checks that an inline constructor given
// for a pointer field is rendered as the address of a composite literal.
func TestRenderValueInlineCtorPointer(t *testing.T) {
	reg := sharedRegistry(t)
	field := mustField(t, reg, "fixtures.Fly", "Target")
	got := renderValue(field.Type, valueOf(t, "fixtures.Waypoint(Lat=1.0, Lon=2.0)"), reg)
	want := `&fixtures.Waypoint{
	Lat: float64(1),
	Lon: float64(2),
}`
	if formatDecl(t, "var x = "+got) != formatDecl(t, "var x = "+want) {
		t.Errorf("renderValue() =\n%s\nwant\n%s", got, want)
	}
}

// TestRenderValueNestedInlineCtor checks that inline constructors are
// rendered recursively, both directly as a field and as array elements,
// and that a nested constructor's unset optional fields are left out.
func TestRenderValueNestedInlineCtor(t *testing.T) {
	reg := sharedRegistry(t)
	field := mustField(t, reg, "fixtures.Fly", "Route")
	value := valueOf(t, `fixtures.Route(
		Start=fixtures.Waypoint(Lat=1.0, Lon=2.0, Name="a"),
		Stops=[fixtures.Waypoint(Lat=3.0, Lon=4.0)])`)
	got := renderValue(field.Type, value, reg)
	want := `fixtures.Route{
	Start: fixtures.Waypoint{
		Lat:  float64(1),
		Lon:  float64(2),
		Name: string("a"),
	},
	Stops: []fixtures.Waypoint{fixtures.Waypoint{
		Lat: float64(3),
		Lon: float64(4),
	}},
}`
	if formatDecl(t, "var x = "+got) != formatDecl(t, "var x = "+want) {
		t.Errorf("renderValue() =\n%s\nwant\n%s", got, want)
	}
}

// TestRenderDefault checks that an optional field's default, written as a
// Go literal or enum constant name, is rendered according to its type.
func TestRenderDefault(t *testing.T) {
	reg := sharedRegistry(t)
	cases := []struct {
		field, value, want string
	}{
		{"Timeout", "3.0", "float32(3.0)"},
		{"Fallback", "ModeActive", "fixtures.ModeActive"},
		{"Fallback", "Active", "fixtures.ModeActive"},
		{"Tag", "LabelAway", "fixtures.LabelAway"},
		{"Tag", "home", `fixtures.Label("home")`},
		{"Note", "hello world", `string("hello world")`},
	}
	for _, c := range cases {
		field := mustField(t, reg, "fixtures.Fly", c.field)
		if got := renderDefault(field.Type, c.value, reg); got != c.want {
			t.Errorf("renderDefault(%s, %s) = %s, want %s", c.field, c.value, got, c.want)
		}
	}
}

// TestRenderConstRejectsNonConstants checks that renderConst only accepts
// bool literals for bool fields and declared constants of an enum type,
// qualified (if at all) the way the mission names the enum's package.
func TestRenderConstRejectsNonConstants(t *testing.T) {
	reg := sharedRegistry(t)
	mode := mustField(t, reg, "fixtures.Fly", "Mode").Type
	enabled := mustField(t, reg, "fixtures.Fly", "Enabled").Type
	target := mustField(t, reg, "fixtures.Fly", "Target").Type
	cases := []struct {
		name  string
		t     types.Type
		ident string
	}{
		{"wrong qualifier", mode, "other.ModeActive"},
		{"undeclared constant", mode, "Bogus"},
		{"non-bool for bool", enabled, "yes"},
		{"non-enum type", target, "home"},
	}
	for _, c := range cases {
		if got, ok := renderConst(c.t, c.ident, reg); ok {
			t.Errorf("%s: renderConst(%s) = %s, true; want false", c.name, c.ident, got)
		}
	}
}

// TestQualifierNamesPackages checks that generated code names a package
// imported by the template by its template name even if the mission
// aliased it, and names every other package as the mission does.
func TestQualifierNamesPackages(t *testing.T) {
	reg := &loader.TypeRegistry{PackToAlias: map[string]string{
		dslPkgPath:      "mydsl",
		"example.com/x": "xx",
	}}
	q := qualifier(reg)
	cases := []struct {
		pkg                *types.Package
		qualified, mission string
	}{
		{types.NewPackage(dslPkgPath, "dsl"), "dsl", "mydsl"},
		{types.NewPackage("example.com/x", "x"), "xx", "xx"},
		{types.NewPackage("example.com/y", "y"), "y", "y"},
	}
	for _, c := range cases {
		if got := q(c.pkg); got != c.qualified {
			t.Errorf("qualifier(%s) = %s, want %s", c.pkg.Path(), got, c.qualified)
		}
		if got := missionName(reg, c.pkg); got != c.mission {
			t.Errorf("missionName(%s) = %s, want %s", c.pkg.Path(), got, c.mission)
		}
	}
}
