package loader

import (
	"strings"
	"testing"

	"github.com/alecthomas/participle/v2/lexer"
	"golang.org/x/tools/go/packages"
)

// TestWithDslImport checks that dslPkgPath is prepended unaliased when it
// isn't imported, and that an explicit import, aliased or not, is kept as
// the only one.
func TestWithDslImport(t *testing.T) {
	other := &PackageRequest{Path: "example.com/other"}
	got := withDslImport([]*PackageRequest{other})
	if len(got) != 2 || got[0].Path != dslPkgPath || got[0].Alias != "" || got[1] != other {
		t.Errorf("withDslImport(other) = %+v, want [dsl other]", got)
	}

	aliased := &PackageRequest{Path: dslPkgPath, Alias: "d"}
	got = withDslImport([]*PackageRequest{other, aliased})
	if len(got) != 2 || got[0] != other || got[1] != aliased {
		t.Errorf("withDslImport(other, aliased dsl) = %+v, want it unchanged", got)
	}
}

// fakePkgs returns loaded packages by import path, each named by name.
func fakePkgs(names map[string]string) map[string]*packages.Package {
	pkgs := map[string]*packages.Package{}
	for path, name := range names {
		pkgs[path] = &packages.Package{PkgPath: path, Name: name}
	}
	return pkgs
}

// TestCheckImports checks which import sets are reported as duplicate or
// conflicting, and that each error is attributed to the later import.
func TestCheckImports(t *testing.T) {
	pkgs := fakePkgs(map[string]string{
		dslPkgPath:            "dsl",
		"example.com/a/util":  "util",
		"example.com/b/util":  "util",
		"example.com/actions": "actions",
		"example.com/my/dsl":  "dsl",
	})
	at := func(line int) lexer.Position { return lexer.Position{Filename: "m.dsl", Line: line} }
	tests := map[string]struct {
		imports []*PackageRequest
		want    string // substring of the single expected error, or "" for none
		line    uint32 // line the error is attributed to
	}{
		"distinct names": {
			imports: []*PackageRequest{{Path: dslPkgPath}, {Path: "example.com/a/util"}, {Path: "example.com/actions"}},
		},
		"same name, one aliased": {
			imports: []*PackageRequest{{Path: "example.com/a/util"}, {Path: "example.com/b/util", Alias: "butil"}},
		},
		"same package name": {
			imports: []*PackageRequest{{Path: "example.com/a/util", Pos: at(2)}, {Path: "example.com/b/util", Pos: at(3)}},
			want:    "example.com/b/util is imported as util, which conflicts with example.com/a/util",
			line:    3,
		},
		"alias equals package name": {
			imports: []*PackageRequest{{Path: "example.com/actions", Pos: at(2)}, {Path: "example.com/a/util", Alias: "actions", Pos: at(3)}},
			want:    "example.com/a/util is imported as actions, which conflicts with example.com/actions",
			line:    3,
		},
		"same alias": {
			imports: []*PackageRequest{{Path: "example.com/a/util", Alias: "u", Pos: at(2)}, {Path: "example.com/b/util", Alias: "u", Pos: at(3)}},
			want:    "imported as u",
			line:    3,
		},
		"duplicate path": {
			imports: []*PackageRequest{{Path: "example.com/a/util", Pos: at(2)}, {Path: "example.com/a/util", Alias: "u", Pos: at(3)}},
			want:    "package example.com/a/util is imported more than once",
			line:    3,
		},
		"conflicts with implicit dsl": {
			imports: withDslImport([]*PackageRequest{{Path: "example.com/my/dsl", Pos: at(2)}}),
			want:    "example.com/my/dsl is imported as dsl, which conflicts with " + dslPkgPath,
			line:    2,
		},
	}
	for name, tc := range tests {
		t.Run(name, func(t *testing.T) {
			errs := checkImports(tc.imports, pkgs)
			if tc.want == "" {
				if len(errs) > 0 {
					t.Errorf("checkImports() errors = %v, want none", errs)
				}
				return
			}
			if len(errs) != 1 || !strings.Contains(errs[0].Error(), tc.want) {
				t.Fatalf("checkImports() errors = %v, want one containing %q", errs, tc.want)
			}
			if errs[0].LineNo != tc.line || errs[0].File != "m.dsl" {
				t.Errorf("error at %s:%d, want m.dsl:%d", errs[0].File, errs[0].LineNo, tc.line)
			}
		})
	}
}
