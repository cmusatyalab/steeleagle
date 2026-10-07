package loader

import (
	"go/types"
	"testing"
)

// TestExtractStructSplitsRequiredAndOptional checks that structFields puts
// an unmarked field in the required slice, an optional field (bare
// "#optional") in the optional slice, and skips unexported fields
// entirely.
func TestExtractStructSplitsRequiredAndOptional(t *testing.T) {
	src := `package fixture

// Hover is a fixture action.
type Hover struct {
	// Duration is how long to hover, in seconds.
	Duration float32
	// #optional
	Altitude float32 // meters above ground
	unexported int
}
`
	tpkg, docTypes := typeCheckFixture(t, "fixture", src)
	_, st := namedStruct(t, tpkg, "Hover")
	fields, optFields := structFields(st, docTypes["Hover"])

	if len(fields) != 1 {
		t.Fatalf("required fields = %v, want exactly 1 (Duration)", fields)
	}
	duration := fieldByName(t, fields, "Duration")
	if want := "Duration is how long to hover, in seconds."; duration.Comment != want {
		t.Errorf("Duration.Comment = %q, want %q", duration.Comment, want)
	}

	if len(optFields) != 1 {
		t.Fatalf("optional fields = %v, want exactly 1 (Altitude)", optFields)
	}
	altitude := fieldByName(t, optFields, "Altitude")
	if want := "meters above ground"; altitude.Comment != want {
		t.Errorf("Altitude.Comment = %q, want %q", altitude.Comment, want)
	}
	if altitude.Value != "" {
		t.Errorf("Altitude.Value = %q, want empty (no bracketed default)", altitude.Value)
	}

	for _, f := range append(fields, optFields...) {
		if f.Name == "unexported" {
			t.Errorf("unexported field leaked into result: %v", f)
		}
	}
}

// TestExtractStructBracketedDefaultAndUnifiedComment checks that an
// "#optional[<value>]" tag both captures its default and is scrubbed from
// the doc text, and that the remaining doc text is joined with the
// field's trailing line comment.
func TestExtractStructBracketedDefaultAndUnifiedComment(t *testing.T) {
	src := `package fixture

type Waypoint struct {
	// Speed to move at. #optional[2.5]
	Speed float32 // must be positive
}
`
	tpkg, docTypes := typeCheckFixture(t, "fixture", src)
	_, st := namedStruct(t, tpkg, "Waypoint")
	fields, optFields := structFields(st, docTypes["Waypoint"])

	if len(fields) != 0 {
		t.Fatalf("required fields = %v, want none", fields)
	}
	speed := fieldByName(t, optFields, "Speed")
	if speed.Value != "2.5" {
		t.Errorf("Speed.Value = %q, want %q", speed.Value, "2.5")
	}
	want := "Speed to move at. Must be positive"
	if speed.Comment != want {
		t.Errorf("Speed.Comment = %q, want %q", speed.Comment, want)
	}
}

// TestExtractStructEmbeddedFieldUsesTypeNameAndComment checks that an
// embedded (anonymous) field is keyed by the embedded type's own name and
// picks up the doc comment written on its embedding line.
func TestExtractStructEmbeddedFieldUsesTypeNameAndComment(t *testing.T) {
	src := `package fixture

// Base holds a name.
type Base struct {
	Name string
}

// Derived adds extra fields on top of Base.
type Derived struct {
	// Base is embedded for its Name field.
	Base
	// #optional
	Extra float32
}
`
	tpkg, docTypes := typeCheckFixture(t, "fixture", src)
	_, st := namedStruct(t, tpkg, "Derived")
	fields, optFields := structFields(st, docTypes["Derived"])

	base := fieldByName(t, fields, "Base")
	if want := "Base is embedded for its Name field."; base.Comment != want {
		t.Errorf("Base.Comment = %q, want %q", base.Comment, want)
	}
	if len(optFields) != 1 || optFields[0].Name != "Extra" {
		t.Errorf("optFields = %v, want exactly [Extra]", optFields)
	}
}

// TestExtractStructNilDocLeavesCommentsEmpty checks that a nil *doc.Type
// (e.g. because go/doc couldn't resolve the declaration) doesn't panic and
// simply leaves every field's Comment/Value empty.
func TestExtractStructNilDocLeavesCommentsEmpty(t *testing.T) {
	src := `package fixture

type Hover struct {
	Duration float32
}
`
	tpkg, _ := typeCheckFixture(t, "fixture", src)
	_, st := namedStruct(t, tpkg, "Hover")
	fields, optFields := structFields(st, nil)

	if len(optFields) != 0 {
		t.Fatalf("optFields = %v, want none", optFields)
	}
	duration := fieldByName(t, fields, "Duration")
	if duration.Comment != "" {
		t.Errorf("Comment = %q, want empty", duration.Comment)
	}
}

// TestExtractEnumReturnsConstsOfMatchingType checks that enumValues collects
// every exported constant declared with the target named type, with Name
// and Value both set to the constant's identifier and Comment unified from
// its doc/line comments, and excludes constants of an unrelated type.
func TestExtractEnumReturnsConstsOfMatchingType(t *testing.T) {
	src := `package fixture

// Mode enumerates flight modes.
type Mode uint32

const (
	// ModeIdle is the default, do-nothing mode.
	ModeIdle Mode = iota
	ModeActive // active flight
)

type Other uint32

const OtherX Other = 1
`
	tpkg, docTypes := typeCheckFixture(t, "fixture", src)
	scope := tpkg.Scope()
	mode, ok := scope.Lookup("Mode").Type().(*types.Named)
	if !ok {
		t.Fatalf("Mode is not a named type")
	}

	values := enumValues(scope, mode, docTypes["Mode"])

	if len(values) != 2 {
		t.Fatalf("values = %v, want exactly 2 (ModeIdle, ModeActive)", values)
	}
	for _, v := range values {
		if v.Value != v.Name {
			t.Errorf("%s: Value = %q, want equal to Name", v.Name, v.Value)
		}
	}
	idle := fieldByName(t, values, "ModeIdle")
	if want := "ModeIdle is the default, do-nothing mode."; idle.Comment != want {
		t.Errorf("ModeIdle.Comment = %q, want %q", idle.Comment, want)
	}
	active := fieldByName(t, values, "ModeActive")
	if want := "active flight"; active.Comment != want {
		t.Errorf("ModeActive.Comment = %q, want %q", active.Comment, want)
	}
	for _, v := range values {
		if v.Name == "OtherX" {
			t.Errorf("constant of unrelated type leaked into result: %v", v)
		}
	}
}

// TestExtractEnumNilDocLeavesCommentsEmpty checks that a nil *doc.Type
// doesn't panic and leaves every value's Comment empty.
func TestExtractEnumNilDocLeavesCommentsEmpty(t *testing.T) {
	src := `package fixture

type Mode uint32

const ModeIdle Mode = 0
`
	tpkg, _ := typeCheckFixture(t, "fixture", src)
	scope := tpkg.Scope()
	mode := scope.Lookup("Mode").Type().(*types.Named)

	values := enumValues(scope, mode, nil)
	idle := fieldByName(t, values, "ModeIdle")
	if idle.Comment != "" {
		t.Errorf("Comment = %q, want empty", idle.Comment)
	}
}
