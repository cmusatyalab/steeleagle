package loader

import (
	"fmt"

	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"golang.org/x/tools/go/packages"
)

// withDslImport returns imports with dslPkgPath prepended, unaliased,
// unless it is already imported under any alias, since every mission needs
// the Action, Event and Datatype interfaces it declares. Prepending it
// means a mission package that is also named dsl is the one reported as
// conflicting.
func withDslImport(imports []*PackageRequest) []*PackageRequest {
	for _, imp := range imports {
		if imp.Path == dslPkgPath {
			return imports
		}
	}
	return append([]*PackageRequest{{Path: dslPkgPath}}, imports...)
}

// checkImports reports every import of a package that is already imported,
// and every import whose qualifier (its alias, or its package name if it
// has none) is already taken by another imported package, since types are
// registered and referenced by that qualifier. pkgs holds the loaded
// packages by import path.
func checkImports(imports []*PackageRequest, pkgs map[string]*packages.Package) []*buildtools.CompileError {
	var errs []*buildtools.CompileError
	paths := map[string]bool{}
	names := map[string]*PackageRequest{}
	for _, imp := range imports {
		if paths[imp.Path] {
			errs = append(errs, importError(imp, "package %s is imported more than once", imp.Path))
			continue
		}
		paths[imp.Path] = true
		name := imp.Alias
		if name == "" {
			pkg, ok := pkgs[imp.Path]
			if !ok {
				continue // load errors are reported separately
			}
			name = pkg.Name
		}
		if prev, ok := names[name]; ok {
			errs = append(errs, importError(imp,
				"package %s is imported as %s, which conflicts with %s; import one of them under a different alias",
				imp.Path, name, prev.Path,
			))
			continue
		}
		names[name] = imp
	}
	return errs
}

// importError returns a compile error attributed to the import imp.
func importError(imp *PackageRequest, format string, args ...any) *buildtools.CompileError {
	return &buildtools.CompileError{
		Err:    fmt.Errorf(format, args...),
		File:   imp.Pos.Filename,
		Decl:   imp.Path,
		LineNo: uint32(imp.Pos.Line),
	}
}
