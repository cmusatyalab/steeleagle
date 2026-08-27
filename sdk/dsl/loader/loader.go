package loader

import (
	"fmt"
	"go/token"
	"go/types"
	"os"
	"strings"

	"github.com/cmusatyalab/steeleagle/sdk"
	"golang.org/x/tools/go/packages"
)

// dslPkgPath is the base DSL package which contains interface
// definitions.
const dslPkgPath = "github.com/cmusatyalab/steeleagle/sdk/dsl"

// PackageRequest represents an import request for a Go package.
// A list of these is passed into the loader to load types.
type PackageRequest struct {
	Path  string // import path
	Alias string // import alias
}

// Field holds a field's type and its comment.
type Field struct {
	Name      string     // name of this field (the const name, for an enum value)
	Comment   string     // comment for this field
	Value     string     // default value of field (for optionals)
	Type      types.Type // type for this field
	Qualifier string     // qualifier for this type
}

// Base holds a base type, its fields, and its comment.
type Base struct {
	Comment   string     // comment for this base object
	Type      types.Type // type for this base object
	Fields    []Field    // list of fields
	OptFields []Field    // list of optional fields
	Qualifier string     // qualifier for this type
}

// TypeRegistry holds all the imported packages and registers types
// within them.
type TypeRegistry struct {
	Packages    map[string]*packages.Package
	AliasToPack map[string]*packages.Package
	PackToAlias map[string]string
	Actions     map[string]*Base
	Events      map[string]*Base
	Datatypes   map[string]*Base
	Enums       map[string]*Base
}

// LoadTypes loads all DSL types present in imports (Actions, Events, and Datatypes).
// Also loads comments and detects optional types by #optional tags.
func LoadTypes(imports []*PackageRequest, workspace string, overlay map[string][]byte) (*TypeRegistry, []*sdk.CompileError) {
	registry := &TypeRegistry{
		Packages:    make(map[string]*packages.Package),
		AliasToPack: make(map[string]*packages.Package),
		PackToAlias: make(map[string]string),
		Actions:     make(map[string]*Base),
		Events:      make(map[string]*Base),
		Datatypes:   make(map[string]*Base),
		Enums:       make(map[string]*Base),
	}
	errors := []*sdk.CompileError{}

	// Create a list of packages to import, remembering each one's alias so
	// it can be attached once the package is actually loaded below.
	pkgPaths := []string{}
	aliases := map[string]string{}
	for _, imp := range imports {
		pkgPaths = append(pkgPaths, imp.Path)
		if imp.Alias != "" {
			aliases[imp.Path] = imp.Alias
		}
	}
	cfg := &packages.Config{
		Dir:     workspace,
		Env:     append(os.Environ(), "GOFLAGS=-mod=mod"),
		Mode:    packages.NeedName | packages.NeedTypes | packages.NeedSyntax,
		Overlay: overlay,
	}
	pkgs, err := packages.Load(cfg, pkgPaths...)
	if err != nil {
		return nil, append(errors, &sdk.CompileError{
			Err: fmt.Errorf("failed to load packages: %w", err),
		})
	}

	// Collect package loading errors and register every loaded package.
	for _, p := range pkgs {
		for _, e := range p.Errors {
			errors = append(errors, packageError(e, p.PkgPath))
		}
		registry.Packages[p.PkgPath] = p
		if alias, ok := aliases[p.PkgPath]; ok {
			registry.AliasToPack[alias] = p
			registry.PackToAlias[p.PkgPath] = alias
		}
	}
	if len(errors) > 0 {
		return nil, errors
	}

	// Lookup the concrete interface definitions in dslPkgPath for
	// Action, Event, and Datatype. Return a compile error and nil if
	// dslPkgPath is not included in the imports or the interfaces cannot
	// be found.
	dslPkg, ok := registry.Packages[dslPkgPath]
	if !ok {
		return nil, append(errors, &sdk.CompileError{
			Err: fmt.Errorf("base dsl package %q was not imported", dslPkgPath),
		})
	}
	interfaces, err := lookupInterfaces(
		dslPkg, []string{"Action", "Event", "Datatype"},
	)
	if err != nil {
		return nil, append(errors, &sdk.CompileError{Err: err, File: dslPkgPath})
	} else if len(interfaces) != 3 {
		return nil, append(errors, &sdk.CompileError{
			Err:  fmt.Errorf("expected 3 interfaces back, got %d instead", len(interfaces)),
			File: dslPkgPath,
		})
	}

	// Pack types into the type registry by interface implementation
	for k, p := range registry.Packages {
		if p.Types == nil {
			continue
		}
		qualifier := p.Types.Name()
		if alias, ok := registry.PackToAlias[k]; ok {
			qualifier = alias
		}
		docTypes := packageDocTypes(p)

		scope := p.Types.Scope()
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
			dt := docTypes[name]
			comment := ""
			if dt != nil {
				comment = strings.TrimSpace(dt.Doc)
			}
			qualifiedName := qualifier + "." + name

			switch st := named.Underlying().(type) {
			case *types.Struct:
				idx, err := implements(named, interfaces)
				if err != nil { // implements more than one interface
					errors = append(errors, &sdk.CompileError{
						Err:  fmt.Errorf("%s implements more than one of Action, Event, and Datatype", qualifiedName),
						File: p.PkgPath,
					})
					continue
				} else if idx < 0 { // doesn't implement any interfaces
					continue
				}
				fields, optFields := structFields(st, dt)
				b := &Base{
					Type:      named,
					Comment:   comment,
					Fields:    fields,
					OptFields: optFields,
				}
				switch idx {
				case 0:
					registry.Actions[qualifiedName] = b
				case 1:
					registry.Events[qualifiedName] = b
				case 2:
					registry.Datatypes[qualifiedName] = b
				}
			case *types.Basic:
				if st.Kind() != types.Uint32 && st.Kind() != types.String {
					continue
				}
				registry.Enums[qualifiedName] = &Base{
					Type:    named,
					Comment: comment,
					Fields:  enumValues(scope, named, dt),
				}
			}
		}
	}

	if len(errors) > 0 {
		return nil, errors
	}
	return registry, nil
}

// lookupInterfaces looks up a list of interface names in pkg's package scope and returns
// them as a slice of interfaces.
func lookupInterfaces(pkg *packages.Package, names []string) ([]*types.Interface, error) {
	ifaces := []*types.Interface{}
	for _, name := range names {
		obj := pkg.Types.Scope().Lookup(name)
		if obj == nil {
			return nil, fmt.Errorf("package %q is missing the %s interface", pkg.PkgPath, name)
		}
		iface, ok := obj.Type().Underlying().(*types.Interface)
		if !ok {
			return nil, fmt.Errorf("%s is not an interface type", name)
		}
		ifaces = append(ifaces, iface)
	}
	return ifaces, nil
}

// implements reports the index of the interface in iface *named satisfies,
// returning -1 if none are satisfied or an error if more than one is
// satisfied.
func implements(named *types.Named, iface []*types.Interface) (int, error) {
	idx := -1
	if named == nil || iface == nil {
		return idx, nil
	}
	for i, inter := range iface {
		if types.Implements(types.NewPointer(named), inter) {
			if idx >= 0 {
				return idx, fmt.Errorf("ambiguous implementation of more than one interface")
			}
			idx = i
		}
	}
	return idx, nil
}
