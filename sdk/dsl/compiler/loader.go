package compiler

import (
	"fmt"
	"go/ast"
	"go/doc"
	"go/token"
	"go/types"
	"path/filepath"
	"strings"

	"golang.org/x/tools/go/packages"
)

// sdkPkgPath is the main SDK package that holds the base types.
const sdkPkgPath = "github.com/cmusatyalab/steeleagle/sdk/"

const (
	dslPkgPath     = sdkPkgPath + "dsl"
	actionsPkgPath = sdkPkgPath + "dsl/actions"
	typesPkgPath   = sdkPkgPath + "dsl/types"
	eventsPkgPath  = sdkPkgPath + "dsl/events"
	enumsPkgPath   = sdkPkgPath + "enums"
)

// steeleaglePkgs are the base packages that are always imported
// and kept under the base namespace.
var steeleaglePkgs = []string{
	dslPkgPath,
	actionsPkgPath,
	typesPkgPath,
	eventsPkgPath,
	enumsPkgPath,
}

// fieldType holds a type of a baseType field.
type fieldType struct {
	Comment string
	Type    types.Type
}

// baseType holds a base type like an Action, Event, or Datatype.
type baseType struct {
	Comment string
	Type    types.Type
	Fields  []*fieldType
}

// enumValue holds an enum name value and its comment.
type enumValue struct {
	Comment string
	Value   string
}

// enumType holds an enum Type and its registered values.
type enumType struct {
	Comment string
	Type    types.Type
	Values  []*enumValue
}

// typeRegistry holds all the imported packages, and registers
// the types within them.
type typeRegistry struct {
	Packages  map[string]*packages.Package
	Alias     map[string]string // aliases for packages
	Actions   map[string]baseType
	Datatypes map[string]baseType
	Events    map[string]baseType
	Enums     map[string]enumType
	Errors    map[string][]string // map from package path to errors
}

// loadPackages loads all packages in to the type registry and populates
// Type maps so that it can be queried later.
func loadPackages(imports []*ImportSpec, workspace string) (*typeRegistry, error) {
	registry := &typeRegistry{
		Packages:  make(map[string]*packages.Package),
		Alias:     make(map[string]string),
		Actions:   make(map[string]baseType),
		Datatypes: make(map[string]baseType),
		Events:    make(map[string]baseType),
		Enums:     make(map[string]enumType),
		Errors:    make(map[string][]string),
	}
	pkgPaths := steeleaglePkgs
	seen := map[string]bool{} // keeps track of which packages we've seen
	for _, p := range pkgPaths {
		seen[p] = true
	}
	for _, imp := range imports { // there are extra packages we need to load
		if !seen[imp.Path] {
			seen[imp.Path] = true
			pkgPaths = append(pkgPaths, imp.Path)
		}
		if imp.Alias != "" {
			registry.Alias[imp.Path] = imp.Alias
		}
	}

	// Configure the Golang package loader
	cfg := &packages.Config{
		Dir: workspace,
		Env: []string{"GOWORK=" + filepath.Join(workspace, "go.work")}, // set the go.work path for local resolutions
		Mode: packages.NeedName | packages.NeedTypes | packages.NeedTypesInfo |
			packages.NeedSyntax | packages.NeedImports | packages.NeedDeps,
	}
	pkgs, err := packages.Load(cfg, pkgPaths...)
	if err != nil {
		return nil, fmt.Errorf("failed to load packages: %w", err)
	}

	// Collect errors for each individual package and add the packages to the
	// package map
	for _, p := range pkgs {
		for _, e := range p.Errors {
			registry.Errors[p.PkgPath] = append(registry.Errors[p.PkgPath], e.Error())
		}
		registry.Packages[p.PkgPath] = p
	}

	// Check to make sure the base DSL package loaded
	dslPkg, ok := registry.Packages[dslPkgPath]
	if !ok {
		return nil, fmt.Errorf("could not load base dsl package")
	}
	if errs, ok := registry.Errors[dslPkgPath]; ok {
		return nil, fmt.Errorf("dsl package loaded with errors: %q", errs)
	}

	// Look up the interfaces for each type
	actionIface, err := lookupInterface(dslPkg, "Action")
	if err != nil {
		return nil, err
	}
	eventIface, err := lookupInterface(dslPkg, "Event")
	if err != nil {
		return nil, err
	}
	datatypeIface, err := lookupInterface(dslPkg, "Datatype")
	if err != nil {
		return nil, err
	}

	// Walk all packages looking for DSL interface implementations
	for _, pkg := range registry.Packages {
		if pkg.Types == nil {
			continue
		}
		qualifier := pkg.Types.Name()
		if alias, ok := registry.Alias[pkg.PkgPath]; ok {
			qualifier = alias
		}

		docTypes := packageDocTypes(pkg)

		scope := pkg.Types.Scope()
		for _, name := range scope.Names() {
			if !token.IsExported(name) {
				continue
			}
			tn, ok := scope.Lookup(name).(*types.TypeName)
			if !ok || tn.IsAlias() {
				continue
			}
			named, ok := tn.Type().(*types.Named)
			if !ok {
				continue
			}
			qualifiedName := qualifier + "." + name
			dt := docTypes[name]
			comment := ""
			if dt != nil {
				comment = strings.TrimSpace(dt.Doc)
			}

			switch st := named.Underlying().(type) {
			case *types.Struct:
				bt := baseType{
					Type:    named,
					Comment: comment,
					Fields:  structFields(st, dt),
				}
				if directlyImplements(named, actionIface) {
					registry.Actions[qualifiedName] = bt
				}
				if directlyImplements(named, eventIface) {
					registry.Events[qualifiedName] = bt
				}
				if directlyImplements(named, datatypeIface) {
					registry.Datatypes[qualifiedName] = bt
				}
			case *types.Basic: // all basic types are classified as enums
				registry.Enums[qualifiedName] = enumType{
					Type:    named,
					Comment: comment,
					Values:  enumValues(scope, named, dt),
				}
			}
		}
	}

	return registry, nil
}

// lookupInterface looks up name in pkg's package scope and returns it as an
// interface type, e.g. the dsl.Action, dsl.Event, or dsl.Datatype interface.
func lookupInterface(pkg *packages.Package, name string) (*types.Interface, error) {
	obj := pkg.Types.Scope().Lookup(name)
	if obj == nil {
		return nil, fmt.Errorf("dsl package %q is missing the %s interface", pkg.PkgPath, name)
	}
	iface, ok := obj.Type().Underlying().(*types.Interface)
	if !ok {
		return nil, fmt.Errorf("dsl.%s is not an interface type", name)
	}
	return iface, nil
}

// directlyImplements reports whether named satisfies iface using only
// named's own explicitly declared methods, ignoring methods promoted from
// embedded fields.
func directlyImplements(named *types.Named, iface *types.Interface) bool {
	if named == nil || iface == nil {
		return false
	}

	// Check each method implemented against the candidate interface
	direct := make(map[string]*types.Func, named.NumMethods())
	for i := 0; i < named.NumMethods(); i++ {
		m := named.Method(i)
		direct[m.Id()] = m
	}
	for i := 0; i < iface.NumMethods(); i++ {
		want := iface.Method(i)
		got, ok := direct[want.Id()]
		if !ok || !types.Identical(got.Type(), want.Type()) {
			return false
		}
	}
	return true
}

// enumValues returns one enumValue per exported package-level constant in
// scope declared with type t, along with each one's doc/line comment (read
// from dt, dt.Consts specifically).
func enumValues(scope *types.Scope, t *types.Named, dt *doc.Type) []*enumValue {
	valueComments := constComments(dt)
	var values []*enumValue
	for _, name := range scope.Names() {
		if !token.IsExported(name) {
			continue
		}
		c, ok := scope.Lookup(name).(*types.Const)
		if !ok {
			continue
		}
		if named, ok := c.Type().(*types.Named); ok && named == t {
			values = append(values, &enumValue{
				Value:   name,
				Comment: valueComments[name],
			})
		}
	}
	return values
}

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

// structFields returns one fieldType per field of st, in declaration order,
// carrying each field's comment (if dt's declaration can be resolved). dt
// may be nil, in which case every field's Comment is empty.
func structFields(st *types.Struct, dt *doc.Type) []*fieldType {
	comments := fieldComments(dt)
	fields := make([]*fieldType, st.NumFields())
	for i := 0; i < st.NumFields(); i++ {
		f := st.Field(i)
		fields[i] = &fieldType{
			Type:    f.Type(),
			Comment: comments[f.Name()],
		}
	}
	return fields
}

// fieldComments returns field name -> doc/line comment text for the struct
// type declared by dt. A field's comment is its leading (Doc) comment if
// present, otherwise its trailing same-line (Comment) comment.
func fieldComments(dt *doc.Type) map[string]string {
	comments := map[string]string{}
	if dt == nil || dt.Decl == nil {
		return comments
	}
	for _, spec := range dt.Decl.Specs {
		ts, ok := spec.(*ast.TypeSpec)
		if !ok || ts.Name.Name != dt.Name {
			continue
		}
		st, ok := ts.Type.(*ast.StructType)
		if !ok || st.Fields == nil {
			return comments
		}
		for _, f := range st.Fields.List {
			text := commentText(f.Doc, f.Comment)
			if text == "" {
				continue
			}
			if len(f.Names) == 0 {
				if name := embeddedFieldName(f.Type); name != "" {
					comments[name] = text
				}
				continue
			}
			for _, id := range f.Names {
				comments[id.Name] = text
			}
		}
		return comments
	}
	return comments // failure case where no comment is found
}

// constComments returns const name -> doc/line comment text for every
// constant go/doc associated with dt (i.e. dt.Consts, the constants
// declared with dt's type).
func constComments(dt *doc.Type) map[string]string {
	comments := map[string]string{}
	if dt == nil {
		return comments
	}
	for _, v := range dt.Consts {
		if v.Decl == nil {
			continue
		}
		for _, spec := range v.Decl.Specs {
			vs, ok := spec.(*ast.ValueSpec)
			if !ok {
				continue
			}
			text := commentText(vs.Doc, vs.Comment)
			if text == "" {
				continue
			}
			for _, id := range vs.Names {
				comments[id.Name] = text
			}
		}
	}
	return comments
}

// commentText returns doc's text if present, else line's, else "".
func commentText(doc, line *ast.CommentGroup) string {
	if doc != nil {
		return strings.TrimSpace(doc.Text())
	}
	if line != nil {
		return strings.TrimSpace(line.Text())
	}
	return ""
}

// embeddedFieldName returns the identifier go/types would use as the field
// name for an embedded (anonymous) struct field declared with expr.
func embeddedFieldName(expr ast.Expr) string {
	switch e := expr.(type) {
	case *ast.Ident:
		return e.Name
	case *ast.SelectorExpr:
		return e.Sel.Name
	case *ast.StarExpr:
		return embeddedFieldName(e.X)
	case *ast.IndexExpr:
		return embeddedFieldName(e.X)
	default:
		return ""
	}
}
