package loader

import (
	"go/doc"
	"strconv"
	"strings"
	"unicode"

	"github.com/cmusatyalab/steeleagle/sdk"
	"golang.org/x/tools/go/packages"
)

// packageDocTypes returns pkg's exported type declarations, keyed by name,
// as computed by go/doc.
func packageDocTypes(pkg *packages.Package) map[string]*doc.Type {
	docTypes := map[string]*doc.Type{}
	if pkg.Fset == nil || len(pkg.Syntax) == 0 {
		return docTypes
	}
	docPkg, err := doc.NewFromFiles(pkg.Fset, pkg.Syntax, pkg.PkgPath, doc.PreserveAST)
	if err != nil {
		return docTypes
	}
	for _, t := range docPkg.Types {
		docTypes[t.Name] = t
	}
	return docTypes
}

// packageError converts a packages.Error (as found on a loaded
// packages.Package's Errors field) into an *sdk.CompileError, recovering
// the offending file and line number from its "file:line[:col]" position
// when one is available.
func packageError(e packages.Error, pkgPath string) *sdk.CompileError {
	file, lineNo := pkgPath, uint32(0)
	if e.Pos != "" && e.Pos != "-" {
		parts := strings.SplitN(e.Pos, ":", 3)
		file = parts[0]
		if len(parts) >= 2 {
			if n, err := strconv.ParseUint(parts[1], 10, 32); err == nil {
				lineNo = uint32(n)
			}
		}
	}
	return &sdk.CompileError{Err: e, File: file, LineNo: lineNo}
}

// unifyComment combines a field's doc comment with its trailing line
// comment into one human-readable comment. When both are present, they're
// joined as two sentences, capitalizing line's first letter if it isn't
// already; when only one is present, it's returned as-is.
func unifyComment(doc, line string) string {
	doc, line = strings.TrimSpace(doc), strings.TrimSpace(line)
	switch {
	case doc == "":
		return line
	case line == "":
		return doc
	default:
		return doc + " " + capitalizeFirst(line)
	}
}

// capitalizeFirst upper-cases s's first rune, leaving the rest untouched.
func capitalizeFirst(s string) string {
	if s == "" {
		return s
	}
	r := []rune(s)
	r[0] = unicode.ToUpper(r[0])
	return string(r)
}
