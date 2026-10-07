package linker

import (
	"fmt"
	"go/types"
	"strconv"

	"github.com/alecthomas/participle/v2/lexer"
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
)

// ImportIR is the import clause intermediate representation.
type ImportIR struct {
	Path    string
	Alias   string
	Version string
	Render  string
}

// ValueIR is a value intermediate representation. Values can be
// a variable declaration (e.g. "Altitude: float32(15)") or a
// transition rule (e.g. "done -> patrol").
type ValueIR struct {
	LValue string
	RValue string
	Render string
}

// TypeIR is a DSL type intermediate representation.
type TypeIR struct {
	Name   string // DSL name, used as the FSM state/event name
	Var    string // Go identifier of the generated variable
	Type   string
	Fields []ValueIR
	Render string
	Stanza loader.Stanza
}

// IsAction reports whether this type was declared in the Actions stanza.
func (t *TypeIR) IsAction() bool {
	return t.Stanza == loader.ActionStanza
}

// IsEvent reports whether this type was declared in the Events stanza.
func (t *TypeIR) IsEvent() bool {
	return t.Stanza == loader.EventStanza
}

// TransitionIR is a DSL transition intermediate representation for
// a given state.
type TransitionIR struct {
	State string
	Rules []ValueIR
}

// IR is an intermediate representation of a DSL mission, linked from
// a parsed AST and a TypeRegistry.
type IR struct {
	Imports     map[string]*ImportIR
	All         map[string]*TypeIR
	AllOrdered  []*TypeIR
	Transitions map[string]*TransitionIR
	Start       string
	Role        string
}

// linker holds the state threaded through linking a single mission.
type linker struct {
	registry *loader.TypeRegistry
	decls    map[string]*TypeIR   // declarations linked so far, by DSL name
	imports  map[string]*ImportIR // packages referenced by rendered code, by path
	errors   []*sdk.CompileError
}

// errorf records a compile error at pos, attributed to decl.
func (l *linker) errorf(pos lexer.Position, decl string, format string, args ...any) {
	l.errors = append(l.errors, &sdk.CompileError{
		Err:    fmt.Errorf(format, args...),
		File:   pos.Filename,
		Decl:   decl,
		LineNo: uint32(pos.Line),
	})
}

// use records every package that type t references as an import, since
// rendered code will name t. Only packages the generated source actually
// references can be imported, since Go rejects unused imports. Each
// package is recorded under the name rendered code uses for it (see
// qualifier), reporting an error if that name is already taken by a
// different package.
func (l *linker) use(pos lexer.Position, decl string, t types.Type) {
	// TypeString calls the qualifier once per package in t; the string
	// it builds is discarded
	types.TypeString(t, func(pkg *types.Package) string {
		path := pkg.Path()
		if _, ok := fixedImports[path]; ok {
			return "" // always imported by the template
		}
		if _, ok := l.imports[path]; ok {
			return ""
		}
		alias := missionName(l.registry, pkg)
		for fixedPath, name := range fixedImports {
			if name == alias {
				l.errorf(pos, decl, "package %s is named %s, which conflicts with %s; import it under an alias", path, alias, fixedPath)
				return ""
			}
		}
		for _, imp := range l.imports {
			if imp.Alias == alias {
				l.errorf(pos, decl, "package %s is named %s, which conflicts with %s; import it under an alias", path, alias, imp.Path)
				return ""
			}
		}
		spec := alias
		if alias == pkg.Name() {
			spec = "" // no need to alias a package by its own name
		}
		l.imports[path] = &ImportIR{
			Path:   path,
			Alias:  alias,
			Render: renderImport(spec, path),
		}
		return ""
	})
}

// linkAttrs checks attrs against the fields of base: every required field
// is set exactly once, no unknown fields are set, and every value matches
// its field's type. decl is the enclosing top-level declaration, used for
// error attribution.
func (l *linker) linkAttrs(decl string, pos lexer.Position, typeName string, base *loader.Base, attrs []*parser.Attr) {
	fields := make(map[string]loader.Field)
	for _, f := range base.Fields {
		fields[f.Name] = f
	}
	for _, f := range base.OptFields {
		fields[f.Name] = f
	}

	seen := make(map[string]bool)
	for _, attr := range attrs {
		field, ok := fields[attr.Key]
		switch {
		case !ok:
			l.errorf(attr.Value.Pos, decl, "%s has no field %s", typeName, attr.Key)
		case seen[attr.Key]:
			l.errorf(attr.Value.Pos, decl, "field %s set more than once", attr.Key)
		default:
			seen[attr.Key] = true
			l.linkValue(decl, field.Type, attr.Value)
		}
	}
	for _, f := range base.Fields {
		if !seen[f.Name] {
			l.errorf(pos, decl, "%s required field %s not present", typeName, f.Name)
		}
	}
	// Unset optional fields with a default are rendered too
	for _, f := range base.OptFields {
		if !seen[f.Name] && f.Value != "" {
			l.use(pos, decl, f.Type)
		}
	}
}

// linkValue checks that v is a valid DSL value for Go type t, recursing
// into arrays and inline constructors.
func (l *linker) linkValue(decl string, t types.Type, v *parser.Value) {
	want := types.TypeString(t, qualifier(l.registry))
	basic, _ := t.Underlying().(*types.Basic)
	switch {
	case v.Float != nil, v.Int != nil:
		if basic == nil || basic.Info()&types.IsNumeric == 0 {
			l.errorf(v.Pos, decl, "number given for %s", want)
		} else if v.Float != nil && basic.Info()&types.IsInteger != 0 {
			l.errorf(v.Pos, decl, "%v given for integer type %s", *v.Float, want)
		} else {
			l.use(v.Pos, decl, t) // rendered as a conversion to t
		}
	case v.String != nil:
		if !isStringKind(t) {
			l.errorf(v.Pos, decl, "string given for %s", want)
		} else {
			l.use(v.Pos, decl, t) // rendered as a conversion to t
		}
	case v.Array != nil:
		elem := elemType(t)
		if elem == nil {
			l.errorf(v.Pos, decl, "array given for %s", want)
			return
		}
		l.use(v.Pos, decl, t) // rendered as a composite literal of t
		for _, e := range v.Array.Elems {
			l.linkValue(decl, elem, e)
		}
	case v.Inline != nil:
		name := string(v.Inline.Type)
		base, ok := l.registry.All[name]
		if !ok || base.Stanza != loader.DatatypeStanza {
			l.errorf(v.Pos, decl, "datatype %s is undefined", name)
			return
		}
		if !types.Identical(derefType(t), base.Type) {
			l.errorf(v.Pos, decl, "%s given for %s", name, want)
			return
		}
		l.use(v.Pos, decl, base.Type) // rendered as a composite literal of base
		l.linkAttrs(decl, v.Pos, name, base, v.Inline.Args)
	case v.Ident != nil:
		if _, ok := renderConst(t, *v.Ident, l.registry); ok {
			l.use(v.Pos, decl, t) // rendered as a constant from t's package
			return
		}
		// Only datatypes declared earlier may be referenced, which also
		// rules out self-references and initialization cycles
		ref, ok := l.decls[*v.Ident]
		if !ok || ref.Stanza != loader.DatatypeStanza {
			l.errorf(v.Pos, decl, "%s is neither a %s constant nor a declared datatype", *v.Ident, want)
			return
		}
		if refType := l.registry.All[ref.Type].Type; !types.Identical(derefType(t), refType) {
			l.errorf(v.Pos, decl, "%s has type %s, but %s is required", *v.Ident, ref.Type, want)
		}
	}
}

// linkType links a single parser declaration against the loader registry.
func (l *linker) linkType(decl *parser.Decl, stanza loader.Stanza) *TypeIR {
	typeName := string(decl.Type)
	// Ensure the type exists in the registry and belongs in this stanza
	base, ok := l.registry.All[typeName]
	if !ok {
		l.errorf(decl.Pos, decl.Name, "type name %s is undefined", typeName)
		return nil
	}
	if base.Stanza != stanza {
		l.errorf(decl.Pos, decl.Name, "%s cannot be declared in this stanza", typeName)
		return nil
	}

	// Check all attributes, recursing into inline constructors
	l.use(decl.Pos, decl.Name, base.Type)
	l.linkAttrs(decl.Name, decl.Pos, typeName, base, decl.Attrs)

	// Render the type then return
	return &TypeIR{
		Name:   decl.Name,
		Var:    varName(decl.Name),
		Type:   typeName,
		Stanza: stanza,
		Render: renderType(decl.Name, typeName, decl.Attrs, l.registry),
	}
}

// linkTransition links a transition block against the linked declarations.
func (l *linker) linkTransition(block *parser.DuringBlock) *TransitionIR {
	ir := &TransitionIR{}
	if val, ok := l.decls[block.Action]; !ok || val.Stanza != loader.ActionStanza {
		l.errorf(block.Pos, block.Action, "declaration %s is not an action", block.Action)
	}
	ir.State = block.Action
	for _, rule := range block.Rules {
		if val, ok := l.decls[rule.Event]; rule.Event != "done" && (!ok || val.Stanza != loader.EventStanza) {
			l.errorf(rule.Pos, rule.Event, "declaration %s is not an event", rule.Event)
		} else if val, ok = l.decls[rule.Next]; !ok || val.Stanza != loader.ActionStanza {
			l.errorf(rule.Pos, rule.Next, "declaration %s is not an action", rule.Next)
		}
		ir.Rules = append(ir.Rules, ValueIR{
			LValue: rule.Event,
			RValue: rule.Next,
			Render: strconv.Quote(rule.Event) + ": " + strconv.Quote(rule.Next),
		})
	}
	return ir
}

// Link links a parsed AST against a DSL type registry to create an
// intermediate representation structure which can then be rendered
// onto a main.go mission template.
func Link(ast *parser.Ast, registry *loader.TypeRegistry) (*IR, []*sdk.CompileError) {
	l := &linker{
		registry: registry,
		decls:    make(map[string]*TypeIR),
		imports:  make(map[string]*ImportIR),
	}
	ir := &IR{
		Imports:     l.imports, // filled in as declarations are rendered
		All:         l.decls,
		Transitions: make(map[string]*TransitionIR),
	}

	// Check that every import was loaded. Imports are not copied into
	// the IR, since Go rejects unused imports: only packages that the
	// rendered declarations reference are imported.
	for _, imp := range ast.Import.Imports {
		if _, ok := registry.Packages[imp.Path]; !ok {
			l.errorf(imp.Pos, imp.Path, "unimported package %s", imp.Path)
		}
	}

	// Populate all types (Data first, so Actions and Events can
	// reference it)
	checkAndLinkType := func(decl *parser.Decl, s loader.Stanza) {
		if _, ok := l.decls[decl.Name]; ok {
			l.errorf(decl.Pos, decl.Name, "duplicate definition %s", decl.Name)
		} else if typeIR := l.linkType(decl, s); typeIR != nil {
			l.decls[decl.Name] = typeIR
			ir.AllOrdered = append(ir.AllOrdered, typeIR)
		}
	}
	for _, decl := range ast.Data.Decls {
		checkAndLinkType(decl, loader.DatatypeStanza)
	}
	for _, decl := range ast.Actions.Decls {
		checkAndLinkType(decl, loader.ActionStanza)
	}
	for _, decl := range ast.Events.Decls {
		checkAndLinkType(decl, loader.EventStanza)
	}

	// Populate all transitions
	if val, ok := l.decls[ast.Mission.Start]; !ok || val.Stanza != loader.ActionStanza {
		// Check to make sure the start state is defined
		l.errorf(ast.Mission.Pos, ast.Mission.Start, "declaration %s is not an action", ast.Mission.Start)
	} else {
		ir.Start = ast.Mission.Start
	}
	for _, block := range ast.Mission.Blocks {
		transitionIR := l.linkTransition(block)
		ir.Transitions[transitionIR.State] = transitionIR
	}

	// Only return the IR if there are no errors
	if len(l.errors) == 0 {
		return ir, nil
	}
	return nil, l.errors
}
