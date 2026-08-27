package loader

import (
	"testing"

	"golang.org/x/tools/go/packages"
)

// TestUnifyCommentBothPresent checks that a doc comment and a trailing line
// comment are joined as two sentences, with the line comment's first
// letter capitalized.
func TestUnifyCommentBothPresent(t *testing.T) {
	got := unifyComment("Duration is how long to hover.", "seconds")
	want := "Duration is how long to hover. Seconds"
	if got != want {
		t.Errorf("unifyComment() = %q, want %q", got, want)
	}
}

// TestUnifyCommentDocOnly checks that a doc comment with no line comment is
// returned as-is.
func TestUnifyCommentDocOnly(t *testing.T) {
	got := unifyComment("Duration is how long to hover.", "")
	if got != "Duration is how long to hover." {
		t.Errorf("unifyComment() = %q, want doc unchanged", got)
	}
}

// TestUnifyCommentLineOnly checks that a line comment with no doc comment
// is returned as-is, without being capitalized (capitalization only
// applies when it's appended after a doc sentence).
func TestUnifyCommentLineOnly(t *testing.T) {
	got := unifyComment("", "seconds")
	if got != "seconds" {
		t.Errorf("unifyComment() = %q, want %q", got, "seconds")
	}
}

// TestUnifyCommentBothEmpty checks that two empty comments produce an
// empty result.
func TestUnifyCommentBothEmpty(t *testing.T) {
	if got := unifyComment("", ""); got != "" {
		t.Errorf("unifyComment() = %q, want empty", got)
	}
}

// TestUnifyCommentTrimsWhitespace checks that leading/trailing whitespace
// on either input is trimmed before joining.
func TestUnifyCommentTrimsWhitespace(t *testing.T) {
	got := unifyComment("  Duration is how long to hover.  ", "  seconds  ")
	want := "Duration is how long to hover. Seconds"
	if got != want {
		t.Errorf("unifyComment() = %q, want %q", got, want)
	}
}

// TestCapitalizeFirst checks that only the first rune is upper-cased and
// the rest of the string is left untouched.
func TestCapitalizeFirst(t *testing.T) {
	cases := map[string]string{
		"":        "",
		"seconds": "Seconds",
		"Seconds": "Seconds",
		"éclair":  "Éclair",
		"a b c":   "A b c",
	}
	for in, want := range cases {
		if got := capitalizeFirst(in); got != want {
			t.Errorf("capitalizeFirst(%q) = %q, want %q", in, got, want)
		}
	}
}

// TestPackageErrorParsesFileAndLine checks that a packages.Error with a
// "file:line:col" position is converted into a CompileError carrying the
// file and line number, with the column dropped.
func TestPackageErrorParsesFileAndLine(t *testing.T) {
	e := packages.Error{
		Pos:  "/tmp/mission/actions.go:12:5",
		Msg:  "undefined: Foo",
		Kind: packages.TypeError,
	}
	ce := packageError(e, "example.com/mission")
	if ce.File != "/tmp/mission/actions.go" {
		t.Errorf("File = %q, want %q", ce.File, "/tmp/mission/actions.go")
	}
	if ce.LineNo != 12 {
		t.Errorf("LineNo = %d, want 12", ce.LineNo)
	}
	if ce.Err.Error() != e.Error() {
		t.Errorf("Err = %v, want wrapping %v", ce.Err, e)
	}
}

// TestPackageErrorParsesFileWithoutColumn checks that a "file:line"
// position (no column) is still parsed correctly.
func TestPackageErrorParsesFileWithoutColumn(t *testing.T) {
	e := packages.Error{Pos: "/tmp/mission/actions.go:7", Msg: "boom"}
	ce := packageError(e, "example.com/mission")
	if ce.File != "/tmp/mission/actions.go" || ce.LineNo != 7 {
		t.Errorf("File/LineNo = %q/%d, want %q/7", ce.File, ce.LineNo, "/tmp/mission/actions.go")
	}
}

// TestPackageErrorMissingPositionFallsBackToPkgPath checks that an error
// with no usable position ("" or "-") falls back to pkgPath as File and
// leaves LineNo zero, instead of failing to parse.
func TestPackageErrorMissingPositionFallsBackToPkgPath(t *testing.T) {
	for _, pos := range []string{"", "-"} {
		e := packages.Error{Pos: pos, Msg: "boom"}
		ce := packageError(e, "example.com/mission")
		if ce.File != "example.com/mission" {
			t.Errorf("Pos=%q: File = %q, want %q", pos, ce.File, "example.com/mission")
		}
		if ce.LineNo != 0 {
			t.Errorf("Pos=%q: LineNo = %d, want 0", pos, ce.LineNo)
		}
	}
}

// TestPackageErrorUnparsableLineNumberFallsBackToZero checks that a
// position whose line segment isn't a valid number leaves LineNo at zero
// rather than propagating a parse error.
func TestPackageErrorUnparsableLineNumberFallsBackToZero(t *testing.T) {
	e := packages.Error{Pos: "/tmp/mission/actions.go:notanumber", Msg: "boom"}
	ce := packageError(e, "example.com/mission")
	if ce.File != "/tmp/mission/actions.go" {
		t.Errorf("File = %q, want %q", ce.File, "/tmp/mission/actions.go")
	}
	if ce.LineNo != 0 {
		t.Errorf("LineNo = %d, want 0", ce.LineNo)
	}
}

// TestPackageDocTypesReturnsExportedTypes checks that packageDocTypes
// collects every exported type declaration in the package, keyed by name.
func TestPackageDocTypesReturnsExportedTypes(t *testing.T) {
	src := "package fixture\n\n" +
		"// Hover is a fixture action.\n" +
		"type Hover struct {\n" +
		"\tDuration float32\n" +
		"}\n\n" +
		"type unexported struct{}\n"
	_, docTypes := typeCheckFixture(t, "fixture", src)
	dt, ok := docTypes["Hover"]
	if !ok {
		t.Fatalf("docTypes[%q] not found, got keys %v", "Hover", docTypes)
	}
	if dt.Doc != "Hover is a fixture action.\n" {
		t.Errorf("Doc = %q, want %q", dt.Doc, "Hover is a fixture action.\n")
	}
	if _, ok := docTypes["unexported"]; ok {
		t.Errorf("docTypes contains unexported type, want it omitted")
	}
}

// TestPackageDocTypesEmptySyntaxReturnsEmptyMap checks that a
// packages.Package with no parsed syntax (e.g. Fset/Syntax unset, as
// happens for a package packages.Load couldn't fully load) yields an
// empty map instead of panicking.
func TestPackageDocTypesEmptySyntaxReturnsEmptyMap(t *testing.T) {
	docTypes := packageDocTypes(&packages.Package{PkgPath: "example.com/broken"})
	if len(docTypes) != 0 {
		t.Errorf("docTypes = %v, want empty", docTypes)
	}
}
