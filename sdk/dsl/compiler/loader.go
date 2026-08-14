package main

import (
	"fmt"
	"go/ast"
	"go/doc"
	"go/token"
	"go/types"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/tools/go/packages"
)

// sdkPkgPath is the main SDK package that holds the base types.
const sdkPkgPath = "github.com/cmusatyalab/steeleagle/sdk/"

const (
	basePkgPath    = "github.com/cmusatyalab/steeleagle/sdk"
	dslPkgPath     = sdkPkgPath + "dsl"
	actionsPkgPath = sdkPkgPath + "dsl/actions"
	typesPkgPath   = sdkPkgPath + "dsl/types"
	eventsPkgPath  = sdkPkgPath + "dsl/events"
	enumsPkgPath   = sdkPkgPath + "enums"
	optPkgPath     = sdkPkgPath + "opt"
)

// steeleaglePkgs are the base packages that are always imported
// and kept under the base namespace.
var steeleaglePkgs = []string{
	basePkgPath,
	dslPkgPath,
	actionsPkgPath,
	typesPkgPath,
	eventsPkgPath,
	enumsPkgPath,
	optPkgPath,
}

// fieldType holds a type of a baseType field.
type fieldType struct {
	Comment string
	Type    types.Type
}

// optionalType holds a single vehicle-capability-gated optional field,
// discovered from one SetName(argType) method on the type argument T of an
// opt.Option[T] (or []opt.Option[T]) field.
type optionalType struct {
	Comment string
	Name    string // e.g. "Altitude", from SetAltitude/WithAltitude
	Type    types.Type
}

// baseType holds a base type like an Action, Event, or Datatype.
type baseType struct {
	Comment string
	Type    types.Type
	Fields  []fieldType
	Options []optionalType
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
	Values  []enumValue
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
// Type maps so that it can be queried later. overlay (as produced by
// scrubPackages) replaces the on-disk content of any file it names, so
// that capability scrubbing is reflected in the loaded types.
func loadPackages(imports []*ImportSpec, workspace string, overlay map[string][]byte) (*typeRegistry, error) {
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
		Env: append(os.Environ(), "GOWORK="+filepath.Join(workspace, "go.work")), // set the go.work path for local resolutions
		Mode: packages.NeedName | packages.NeedTypes | packages.NeedTypesInfo |
			packages.NeedSyntax | packages.NeedImports | packages.NeedDeps,
		Overlay: overlay,
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

	// Look up opt.Option, used to recognize a DSL type's optional
	// (vehicle-capability-gated) fields.
	optPkg, ok := registry.Packages[optPkgPath]
	if !ok {
		return nil, fmt.Errorf("could not load base opt package")
	}
	optionType, err := lookupNamedType(optPkg, "Option")
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

		docTypes, _ := getPackageDoc(pkg)

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
					Options: structOptions(st, optionType, registry.Packages),
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

// lookupNamedType looks up name in pkg's package scope and returns it as a
// *types.Named. For a generic type declaration (e.g. opt.Option[T any]),
// this is its generic, uninstantiated form.
func lookupNamedType(pkg *packages.Package, name string) (*types.Named, error) {
	obj := pkg.Types.Scope().Lookup(name)
	if obj == nil {
		return nil, fmt.Errorf("package %q is missing %s", pkg.PkgPath, name)
	}
	tn, ok := obj.(*types.TypeName)
	if !ok {
		return nil, fmt.Errorf("%s in package %q is not a type", name, pkg.PkgPath)
	}
	named, ok := tn.Type().(*types.Named)
	if !ok {
		return nil, fmt.Errorf("%s in package %q is not a named type", name, pkg.PkgPath)
	}
	return named, nil
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
func enumValues(scope *types.Scope, t *types.Named, dt *doc.Type) []enumValue {
	valueComments := constComments(dt)
	var values []enumValue
	for _, name := range scope.Names() {
		if !token.IsExported(name) {
			continue
		}
		c, ok := scope.Lookup(name).(*types.Const)
		if !ok {
			continue
		}
		if named, ok := c.Type().(*types.Named); ok && named == t {
			values = append(values, enumValue{
				Value:   name,
				Comment: valueComments[name],
			})
		}
	}
	return values
}

// structFields returns one fieldType per field of st, in declaration order,
// carrying each field's comment (if dt's declaration can be resolved). dt
// may be nil, in which case every field's Comment is empty.
func structFields(st *types.Struct, dt *doc.Type) []fieldType {
	comments := fieldComments(dt)
	fields := make([]fieldType, st.NumFields())
	for i := 0; i < st.NumFields(); i++ {
		f := st.Field(i)
		fields[i] = fieldType{
			Type:    f.Type(),
			Comment: comments[f.Name()],
		}
	}
	return fields
}

// structOptions scans st's fields for one whose type is an instantiation
// of optionType (opt.Option[T]), either directly or as a slice element
// (opt.Option[T] or []opt.Option[T]), and returns the optionalTypes found.
func structOptions(st *types.Struct, optionType *types.Named, pkgs map[string]*packages.Package) []optionalType {
	var opts []optionalType
	for i := 0; i < st.NumFields(); i++ {
		t := st.Field(i).Type()
		if slice, ok := t.(*types.Slice); ok {
			t = slice.Elem()
		}
		named, ok := t.(*types.Named)
		if !ok || named.Origin() != optionType.Origin() {
			continue
		}
		targs := named.TypeArgs()
		if targs == nil || targs.Len() != 1 {
			continue
		}
		opts = append(opts, optionsFromConstraint(targs.At(0), pkgs)...)
	}
	return opts
}

// optionsFromConstraint walks t's method set (t is the type argument of an
// opt.Option[T] field) for single-argument, no-result SetName(argType)
// methods, and returns one optionalType per method found. Each method's
// comment comes from the WithName function's doc comment, looked up in
// whichever package actually declares the SetName method - not
// necessarily the package of the DSL type the option was found on.
func optionsFromConstraint(t types.Type, pkgs map[string]*packages.Package) []optionalType {
	ms := types.NewMethodSet(t)
	var opts []optionalType
	for i := 0; i < ms.Len(); i++ {
		fn, ok := ms.At(i).Obj().(*types.Func)
		if !ok {
			continue // TODO: log this
		}
		name, ok := strings.CutPrefix(fn.Name(), "Set")
		if !ok || name == "" {
			continue // TODO: log this
		}
		sig, ok := fn.Type().(*types.Signature)
		if !ok || sig.Params().Len() != 1 || sig.Results().Len() != 0 {
			continue // TODO: log this
		}

		comment := ""
		if fn.Pkg() != nil {
			if pkg, ok := pkgs[fn.Pkg().Path()]; ok {
				_, funcs := getPackageDoc(pkg)
				if df, ok := funcs["With"+name]; ok {
					comment = strings.TrimSpace(df.Doc)
					// Remove "With" from the start of the comment
					comment, _ = strings.CutPrefix(comment, "With")
				}
			}
		}

		opts = append(opts, optionalType{
			Comment: comment,
			Name:    name,
			Type:    sig.Params().At(0).Type(),
		})
	}
	return opts
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
