package linker

import (
	"go/types"
	"strconv"
	"strings"

	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
)

// varPrefix is prepended to every DSL declaration name to form its Go
// identifier, so a mission's names can never collide with a Go keyword,
// an import, or a local variable in the generated main().
const varPrefix = "decl_"

// fixedImports are the packages main.go.tmpl always imports, keyed by
// import path, with the identifier each is referenced by. This must be
// kept in sync with main.go.tmpl.
var fixedImports = map[string]string{
	"context":                "context",
	"os":                     "os",
	"os/signal":              "signal",
	"syscall":                "syscall",
	"github.com/rs/zerolog":  "zerolog",
	"google.golang.org/grpc": "grpc",
	"google.golang.org/grpc/credentials/insecure":     "insecure",
	"github.com/cmusatyalab/steeleagle/sdk":           "sdk",
	"github.com/cmusatyalab/steeleagle/sdk/dsl":       "dsl",
	"github.com/cmusatyalab/steeleagle/sdk/dsl/fsm":   "fsm",
	"github.com/cmusatyalab/steeleagle/sdk/dsl/swarm": "swarm",
	"github.com/cmusatyalab/steeleagle/sdk/geo":       "geo",
}

// varName returns the Go identifier for a DSL declaration.
func varName(name string) string {
	return varPrefix + name
}

// renderImport renders a single import spec (e.g. `act "github.com/..."`).
func renderImport(alias string, path string) string {
	if alias == "" {
		return strconv.Quote(path)
	}
	return alias + " " + strconv.Quote(path)
}

// renderType renders a composite literal of the registry type typeName
// from a list of DSL attributes, recursively rendering any inline
// constructors among them. If name is non-empty, the literal is rendered
// as a package-level variable declaration (e.g. "var decl_takeoff = actions.TakeOff{...}").
// Unset optional fields are only rendered when they have a default.
// Attributes are assumed to have already been checked by the linker.
func renderType(name string, typeName string, attrs []*parser.Attr, registry *loader.TypeRegistry) string {
	base := registry.All[typeName]
	attrMap := make(map[string]*parser.Value)
	for _, attr := range attrs {
		attrMap[attr.Key] = attr.Value
	}

	var elems []string
	if base != nil {
		// Render the type name from the Go type, so it is qualified the
		// same way as its import regardless of how the mission wrote it
		typeName = types.TypeString(base.Type, qualifier(registry))
		for _, field := range base.Fields {
			if value, ok := attrMap[field.Name]; ok {
				elems = append(elems, field.Name+": "+renderValue(field.Type, value, registry))
			}
		}
		for _, field := range base.OptFields {
			if value, ok := attrMap[field.Name]; ok {
				elems = append(elems, field.Name+": "+renderValue(field.Type, value, registry))
			} else if field.Value != "" {
				elems = append(elems, field.Name+": "+renderDefault(field.Type, field.Value, registry))
			}
		}
	}

	var sb strings.Builder
	if name != "" {
		sb.WriteString("var " + varName(name) + " = ")
	}
	sb.WriteString(typeName + "{")
	if len(elems) > 0 {
		sb.WriteString("\n")
		for _, elem := range elems {
			sb.WriteString("\t" + elem + ",\n")
		}
	}
	sb.WriteString("}")
	return sb.String()
}

// renderValue renders a DSL value as a Go expression of type t.
func renderValue(t types.Type, v *parser.Value, registry *loader.TypeRegistry) string {
	if t == nil || v == nil {
		return ""
	}
	typeName := types.TypeString(t, qualifier(registry))
	switch {
	case v.Float != nil:
		return typeName + "(" + strconv.FormatFloat(*v.Float, 'g', -1, 64) + ")"
	case v.Int != nil:
		return typeName + "(" + strconv.FormatInt(*v.Int, 10) + ")"
	case v.String != nil:
		s, _ := v.StringValue()
		return typeName + "(" + strconv.Quote(s) + ")"
	case v.Array != nil:
		elem := elemType(t)
		elems := make([]string, len(v.Array.Elems))
		for i, e := range v.Array.Elems {
			elems[i] = renderValue(elem, e, registry)
		}
		return typeName + "{" + strings.Join(elems, ", ") + "}"
	case v.Inline != nil:
		lit := renderType("", string(v.Inline.Type), v.Inline.Args, registry)
		if _, ok := t.(*types.Pointer); ok {
			return "&" + lit
		}
		return lit
	case v.Ident != nil:
		if expr, ok := renderConst(t, *v.Ident, registry); ok {
			return expr
		}
		// Otherwise, this is a reference to a Data declaration
		if _, ok := t.(*types.Pointer); ok {
			return "&" + varName(*v.Ident)
		}
		return varName(*v.Ident)
	default:
		return ""
	}
}

// renderDefault renders an optional field's "#optional[<value>]" default,
// which is written as a Go literal or enum constant name rather than as a
// DSL value.
func renderDefault(t types.Type, value string, registry *loader.TypeRegistry) string {
	if expr, ok := renderConst(t, value, registry); ok {
		return expr
	}
	typeName := types.TypeString(t, qualifier(registry))
	if isStringKind(t) {
		return typeName + "(" + strconv.Quote(value) + ")"
	}
	return typeName + "(" + value + ")"
}

// renderConst renders ident as a constant of type t, if it is one: either
// a bool literal or an enum constant. Enum constants may be written bare
// ("Corridor"), with the type name prefix ("PatrolModeCorridor"), or
// qualified the way the mission names the package ("actions.PatrolModeCorridor").
func renderConst(t types.Type, ident string, registry *loader.TypeRegistry) (string, bool) {
	if basic, ok := t.Underlying().(*types.Basic); ok && basic.Info()&types.IsBoolean != 0 {
		return ident, ident == "true" || ident == "false"
	}
	named, ok := t.(*types.Named)
	if !ok || named.Obj().Pkg() == nil {
		return "", false
	}
	pkg := named.Obj().Pkg()
	pkgName := missionName(registry, pkg)
	short := ident
	if dot := strings.LastIndex(ident, "."); dot >= 0 {
		if ident[:dot] != pkgName {
			return "", false
		}
		short = ident[dot+1:]
	}
	enum, ok := registry.Enums[pkgName+"."+named.Obj().Name()]
	if !ok {
		return "", false
	}
	for _, f := range enum.Fields {
		if f.Name == short || f.Name == named.Obj().Name()+short {
			return qualifier(registry)(pkg) + "." + f.Name, true
		}
	}
	return "", false
}

// missionName returns the name the mission and the loader use for pkg:
// its import alias if one was given, and its package name otherwise.
func missionName(registry *loader.TypeRegistry, pkg *types.Package) string {
	if alias, ok := registry.PackToAlias[pkg.Path()]; ok {
		return alias
	}
	return pkg.Name()
}

// qualifier returns a go/types qualifier for generated source. Packages
// imported by main.go.tmpl are named as the template imports them, and
// all others are named as the mission does.
func qualifier(registry *loader.TypeRegistry) types.Qualifier {
	return func(pkg *types.Package) string {
		if name, ok := fixedImports[pkg.Path()]; ok {
			return name
		}
		return missionName(registry, pkg)
	}
}

// derefType returns the element type of a pointer, or t itself.
func derefType(t types.Type) types.Type {
	if p, ok := t.(*types.Pointer); ok {
		return p.Elem()
	}
	return t
}

// elemType returns the element type of a slice or array, or nil.
func elemType(t types.Type) types.Type {
	switch s := t.Underlying().(type) {
	case *types.Slice:
		return s.Elem()
	case *types.Array:
		return s.Elem()
	default:
		return nil
	}
}

// isStringKind reports whether t's underlying type is a string.
func isStringKind(t types.Type) bool {
	basic, ok := t.Underlying().(*types.Basic)
	return ok && basic.Info()&types.IsString != 0
}
