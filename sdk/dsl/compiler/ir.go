// ir.go turns a parsed DSL Ast plus a loaded TypeRegistry into the plain
// data (IRResult) that generate.go feeds into the main.go template: one
// entry per top-level Data/Actions/Events declaration, only carrying the
// fields the mission actually set or that have a declared default, plus
// the action/event wiring and transition table for the Mission stanza.
package compiler

import (
	"fmt"
	"go/token"
	"go/types"
	"sort"
	"strconv"
	"strings"

	"github.com/alecthomas/participle/v2/lexer"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
)

// posPrefix formats pos as an error-message prefix ("line:col: "), or ""
// when pos is the zero value. A graph-built AST (see graph.go) never sets
// Pos, since there's no source text to derive one from; a real lexed
// position is never the zero value (participle's lexer starts at 1:1), so
// this exactly distinguishes "has a real position" from "doesn't."
func posPrefix(pos lexer.Position) string {
	if pos == (lexer.Position{}) {
		return ""
	}
	return pos.String() + ": "
}

// VarDecl is one generated `var <Name> = <TypeExpr>{ ... }` declaration.
type VarDecl struct {
	Name   string
	Type   string
	Fields []Entry
}

// Entry is a rendered "Name: Value" pair. It covers three template uses:
// a composite literal field ("Altitude: float32(15),"), an actions/events
// map entry ("\"takeoff\": &takeoff,"), and a transition rule
// ("\"done\": \"patrol\","); each range site in main.go.tmpl decides
// whether Name/Value need quoting for its own syntax.
type Entry struct {
	Name  string
	Value string
}

// TransitionEntry is one action's outgoing rules, keyed by the action's
// declared DSL name (its FSM state name).
type TransitionEntry struct {
	State string
	Rules []Entry
}

// ImportEntry is one aliased import the generated file needs beyond the
// fixed set the template hard-codes.
type ImportEntry struct {
	Alias string
	Path  string
}

// IRResult is everything generate.go needs to render main.go.tmpl.
type IRResult struct {
	Imports     []ImportEntry
	Vars        []VarDecl
	Actions     []Entry
	Events      []Entry
	Transitions []TransitionEntry
	Start       string
	Role        string
}

// fixedImports are the packages main.go.tmpl always imports by hand, so
// BuildIR's own qualifier assignment must never reuse (or re-emit) these.
var fixedImports = map[string]string{
	"context": "context",
	"fmt":     "fmt",
	"os":      "os",
	"signal":  "os/signal",
	"syscall": "syscall",

	"grpc":     "google.golang.org/grpc",
	"insecure": "google.golang.org/grpc/credentials/insecure",

	"sdk":   "github.com/cmusatyalab/steeleagle/sdk",
	"dsl":   "github.com/cmusatyalab/steeleagle/sdk/dsl",
	"fsm":   "github.com/cmusatyalab/steeleagle/sdk/dsl/fsm",
	"swarm": "github.com/cmusatyalab/steeleagle/sdk/dsl/swarm",
	"geo":   "github.com/cmusatyalab/steeleagle/sdk/geo",
}

// qualifiers assigns each referenced package an identifier for use in
// generated source, preferring the alias the mission's own Import stanza
// used (registry.PackToAlias) so generated references read the same way
// the mission does.
type qualifiers struct {
	userAliases map[string]string
	pkgAlias    map[string]string
	aliasTaken  map[string]bool
}

func newQualifiers(userAliases map[string]string) *qualifiers {
	q := &qualifiers{
		userAliases: userAliases,
		pkgAlias:    map[string]string{},
		aliasTaken:  map[string]bool{},
	}
	for alias, path := range fixedImports {
		q.pkgAlias[path] = alias
		q.aliasTaken[alias] = true
	}
	return q
}

// qualifier returns pkg's chosen identifier for generated source,
// registering it (and its import path) the first time it's seen. It
// satisfies go/types.Qualifier.
func (q *qualifiers) qualifier(pkg *types.Package) string {
	if pkg == nil {
		return ""
	}
	path := pkg.Path()
	if alias, ok := q.pkgAlias[path]; ok {
		return alias
	}
	alias := q.userAliases[path]
	if alias == "" {
		alias = pkg.Name()
	}
	for q.aliasTaken[alias] {
		alias += "_"
	}
	q.aliasTaken[alias] = true
	q.pkgAlias[path] = alias
	return alias
}

func (q *qualifiers) typeString(t types.Type) string {
	return types.TypeString(t, q.qualifier)
}

// dynamicImports returns every package qualifier touched beyond
// fixedImports, sorted by import path for reproducible output.
func (q *qualifiers) dynamicImports() []ImportEntry {
	var out []ImportEntry
	for path, alias := range q.pkgAlias {
		if _, fixed := fixedImportPaths[path]; fixed {
			continue
		}
		out = append(out, ImportEntry{Alias: alias, Path: path})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Path < out[j].Path })
	return out
}

var fixedImportPaths = func() map[string]bool {
	m := make(map[string]bool, len(fixedImports))
	for _, path := range fixedImports {
		m[path] = true
	}
	return m
}()

// irBuilder holds the state threaded through BuildIR: the registry decls
// resolve against, the qualifiers assigned so far, and every top-level
// var name declared so far (so a later Ident can cross-reference it).
type irBuilder struct {
	registry *loader.TypeRegistry
	q        *qualifiers
	declared map[string]bool
}

// BuildIR resolves ast's Data/Actions/Events/Mission stanzas against
// registry, in that order (so an Actions/Events decl can reference a
// Data decl by name), producing the plain data generate.go renders.
func BuildIR(ast *parser.Ast, registry *loader.TypeRegistry) (*IRResult, error) {
	b := &irBuilder{
		registry: registry,
		q:        newQualifiers(registry.PackToAlias),
		declared: map[string]bool{},
	}

	var vars []VarDecl
	if ast.Data != nil {
		for _, d := range ast.Data.Decls {
			v, err := b.addDecl("datatype", d)
			if err != nil {
				return nil, err
			}
			vars = append(vars, *v)
		}
	}

	actionNames := map[string]bool{}
	var actions []Entry
	if ast.Actions != nil {
		for _, d := range ast.Actions.Decls {
			v, err := b.addDecl("action", d)
			if err != nil {
				return nil, err
			}
			vars = append(vars, *v)
			actions = append(actions, Entry{Name: d.Name, Value: "&" + v.Name})
			actionNames[d.Name] = true
		}
	}

	eventNames := map[string]bool{}
	var events []Entry
	if ast.Events != nil {
		for _, d := range ast.Events.Decls {
			v, err := b.addDecl("event", d)
			if err != nil {
				return nil, err
			}
			vars = append(vars, *v)
			events = append(events, Entry{Name: d.Name, Value: "&" + v.Name})
			eventNames[d.Name] = true
		}
	}

	if ast.Mission == nil {
		return nil, fmt.Errorf("mission is missing a Mission stanza")
	}
	if !actionNames[ast.Mission.Start] {
		return nil, fmt.Errorf("%smission start %q is not a declared action", posPrefix(ast.Mission.Pos), ast.Mission.Start)
	}

	rulesByAction := map[string][]Entry{}
	var actionOrder []string
	for _, blk := range ast.Mission.Blocks {
		if !actionNames[blk.Action] {
			return nil, fmt.Errorf("%sDuring %q is not a declared action", posPrefix(blk.Pos), blk.Action)
		}
		if _, seen := rulesByAction[blk.Action]; !seen {
			actionOrder = append(actionOrder, blk.Action)
		}
		for _, r := range blk.Rules {
			if r.Event != "done" && !eventNames[r.Event] {
				return nil, fmt.Errorf("%sevent %q is not a declared event", posPrefix(r.Pos), r.Event)
			}
			if !actionNames[r.Next] {
				return nil, fmt.Errorf("%stransition target %q is not a declared action", posPrefix(r.Pos), r.Next)
			}
			for _, existing := range rulesByAction[blk.Action] {
				if existing.Name == r.Event {
					return nil, fmt.Errorf("%sevent %q already has a transition from %q", posPrefix(r.Pos), r.Event, blk.Action)
				}
			}
			rulesByAction[blk.Action] = append(rulesByAction[blk.Action], Entry{Name: r.Event, Value: r.Next})
		}
	}
	var transitions []TransitionEntry
	for _, action := range actionOrder {
		transitions = append(transitions, TransitionEntry{State: action, Rules: rulesByAction[action]})
	}

	role := ""
	if ast.Role != nil {
		role = ast.Role.Name
	}

	return &IRResult{
		Imports:     b.q.dynamicImports(),
		Vars:        vars,
		Actions:     actions,
		Events:      events,
		Transitions: transitions,
		Start:       ast.Mission.Start,
		Role:        role,
	}, nil
}

// addDecl resolves decl against registry's kind bucket ("datatype",
// "action", or "event"), records decl.Name as declared, and returns its
// rendered var declaration.
func (b *irBuilder) addDecl(kind string, decl *parser.Decl) (*VarDecl, error) {
	base, ok := lookupBase(b.registry, kind, string(decl.Type))
	if !ok {
		return nil, fmt.Errorf("%sunknown %s type %q", posPrefix(decl.Pos), kind, decl.Type)
	}
	if b.declared[decl.Name] {
		return nil, fmt.Errorf("%s%q is declared more than once", posPrefix(decl.Pos), decl.Name)
	}
	fields, err := b.resolveFields(decl.Pos, base.Fields, base.OptFields, decl.Attrs)
	if err != nil {
		return nil, err
	}
	b.declared[decl.Name] = true
	return &VarDecl{Name: varName(decl.Name), Type: b.q.typeString(base.Type), Fields: fields}, nil
}

// lookupBase looks up name in registry's kind bucket ("action", "event",
// or "datatype").
func lookupBase(registry *loader.TypeRegistry, kind, name string) (*loader.Base, bool) {
	switch kind {
	case "action":
		b, ok := registry.Actions[name]
		return b, ok
	case "event":
		b, ok := registry.Events[name]
		return b, ok
	case "datatype":
		b, ok := registry.Datatypes[name]
		return b, ok
	default:
		return nil, false
	}
}

// resolveFields matches attrs against required/optional, only emitting a
// field when it was explicitly set or (for an optional field left unset)
// when it declares a default value -- everything else is left to its Go
// zero value by omission from the composite literal.
func (b *irBuilder) resolveFields(pos lexer.Position, required, optional []loader.Field, attrs []*parser.Attr) ([]Entry, error) {
	given := map[string]*parser.Value{}
	for _, a := range attrs {
		if _, dup := given[a.Key]; dup {
			return nil, fmt.Errorf("%sfield %q set more than once", posPrefix(pos), a.Key)
		}
		given[a.Key] = a.Value
	}
	known := map[string]loader.Field{}
	for _, f := range required {
		known[f.Name] = f
	}
	for _, f := range optional {
		known[f.Name] = f
	}
	for key := range given {
		if _, ok := known[key]; !ok {
			return nil, fmt.Errorf("%sunknown field %q", posPrefix(pos), key)
		}
	}

	var out []Entry
	for _, f := range required {
		v, ok := given[f.Name]
		if !ok {
			return nil, fmt.Errorf("%smissing required field %q", posPrefix(pos), f.Name)
		}
		expr, err := b.resolveValue(f.Type, v)
		if err != nil {
			return nil, err
		}
		out = append(out, Entry{Name: f.Name, Value: expr})
	}
	for _, f := range optional {
		if v, ok := given[f.Name]; ok {
			expr, err := b.resolveValue(f.Type, v)
			if err != nil {
				return nil, err
			}
			out = append(out, Entry{Name: f.Name, Value: expr})
			continue
		}
		// f.Value carries an optional field's "#optional[value]" default
		// literal ("" when the field has no declared default).
		if f.Value != "" {
			out = append(out, Entry{Name: f.Name, Value: b.renderDefault(f.Type, f.Value)})
		}
	}
	return out, nil
}

// renderDefault renders an optional field's "#optional[value]" default,
// quoting value when the field's type is string-kinded and leaving it
// bare (a numeric or bool literal) otherwise.
func (b *irBuilder) renderDefault(t types.Type, value string) string {
	if isStringKind(t) {
		return fmt.Sprintf("%s(%s)", b.q.typeString(t), strconv.Quote(value))
	}
	return fmt.Sprintf("%s(%s)", b.q.typeString(t), value)
}

func isStringKind(t types.Type) bool {
	basic, ok := t.Underlying().(*types.Basic)
	return ok && basic.Info()&types.IsString != 0
}

// resolveValue renders v as a Go expression of type want.
func (b *irBuilder) resolveValue(want types.Type, v *parser.Value) (string, error) {
	switch {
	case v.Float != nil:
		return fmt.Sprintf("%s(%s)", b.q.typeString(want), strconv.FormatFloat(*v.Float, 'g', -1, 64)), nil
	case v.Int != nil:
		return fmt.Sprintf("%s(%d)", b.q.typeString(want), *v.Int), nil
	case v.String != nil:
		s, _ := v.StringValue()
		return fmt.Sprintf("%s(%s)", b.q.typeString(want), strconv.Quote(s)), nil
	case v.Array != nil:
		elem, ok := sliceElem(want)
		if !ok {
			return "", fmt.Errorf("%sarray value given for non-array field", posPrefix(v.Pos))
		}
		var sb strings.Builder
		fmt.Fprintf(&sb, "%s{\n", b.q.typeString(want))
		for _, e := range v.Array.Elems {
			expr, err := b.resolveValue(elem, e)
			if err != nil {
				return "", err
			}
			fmt.Fprintf(&sb, "%s,\n", expr)
		}
		sb.WriteString("}")
		return sb.String(), nil
	case v.Inline != nil:
		return b.resolveInline(want, v.Inline, v.Pos)
	case v.Ident != nil:
		return b.resolveIdent(want, *v.Ident, v.Pos)
	default:
		return "", fmt.Errorf("%sempty value", posPrefix(v.Pos))
	}
}

// resolveInline renders ctor as a nested composite literal for a
// registered Datatype, taking its address when want expects a pointer.
func (b *irBuilder) resolveInline(want types.Type, ctor *parser.InlineCtor, pos lexer.Position) (string, error) {
	base, ok := lookupBase(b.registry, "datatype", string(ctor.Type))
	if !ok {
		return "", fmt.Errorf("%sunknown datatype %q", posPrefix(pos), ctor.Type)
	}
	fields, err := b.resolveFields(pos, base.Fields, base.OptFields, ctor.Args)
	if err != nil {
		return "", err
	}
	var sb strings.Builder
	fmt.Fprintf(&sb, "%s{\n", b.q.typeString(base.Type))
	for _, f := range fields {
		fmt.Fprintf(&sb, "%s: %s,\n", f.Name, f.Value)
	}
	sb.WriteString("}")
	if _, wantsPointer := want.(*types.Pointer); wantsPointer {
		return "&" + sb.String(), nil
	}
	return sb.String(), nil
}

// resolveIdent renders an identifier -- bare ("Corridor") or
// package-qualified ("params.Poly") -- first trying it as an enum
// constant of want's type, then (bare only; a cross-reference is always to
// a name in this same generated file, never another package) as a
// cross-reference to a previously declared top-level var.
func (b *irBuilder) resolveIdent(want types.Type, ident string, pos lexer.Position) (string, error) {
	if expr, ok := b.resolveEnumConst(want, ident); ok {
		return expr, nil
	}
	if !strings.Contains(ident, ".") && b.declared[ident] {
		expr := varName(ident)
		if _, wantsPointer := want.(*types.Pointer); wantsPointer {
			expr = "&" + expr
		}
		return expr, nil
	}
	return "", fmt.Errorf("%s%q is neither a known enum value nor a previously declared name", posPrefix(pos), ident)
}

// resolveEnumConst looks up want's enum values in the registry (matching
// the same package+name qualification the loader used to key
// registry.Enums) and returns a qualified reference to the one named
// ident, matching it three ways: bare ("Corridor"), bare with want's own
// type name prefixed ("Corridor" matching the constant
// "PatrolModeCorridor"), or package-qualified ("params.Poly"), whose
// qualifier must equal the mission's own qualifier for want's package (the
// alias its Import stanza gave it, or the package's real name if it used
// none) -- the same convention a Decl's Type uses.
func (b *irBuilder) resolveEnumConst(want types.Type, ident string) (string, bool) {
	named, ok := underlyingNamed(want)
	if !ok {
		return "", false
	}
	obj := named.Obj()
	pkg := obj.Pkg()
	if pkg == nil {
		return "", false
	}
	qualifier := pkg.Name()
	if alias, ok := b.registry.PackToAlias[pkg.Path()]; ok {
		qualifier = alias
	}

	short := ident
	if dot := strings.LastIndex(ident, "."); dot >= 0 {
		if ident[:dot] != qualifier {
			return "", false
		}
		short = ident[dot+1:]
	}

	enumBase, ok := b.registry.Enums[qualifier+"."+obj.Name()]
	if !ok {
		return "", false
	}
	for _, f := range enumBase.Fields {
		if f.Name == short || f.Name == obj.Name()+short {
			return b.q.qualifier(pkg) + "." + f.Name, true
		}
	}
	return "", false
}

func underlyingNamed(t types.Type) (*types.Named, bool) {
	if p, ok := t.(*types.Pointer); ok {
		t = p.Elem()
	}
	n, ok := t.(*types.Named)
	return n, ok
}

func sliceElem(t types.Type) (types.Type, bool) {
	if p, ok := t.(*types.Pointer); ok {
		t = p.Elem()
	}
	switch s := t.Underlying().(type) {
	case *types.Slice:
		return s.Elem(), true
	case *types.Array:
		return s.Elem(), true
	default:
		return nil, false
	}
}

// varName returns the package-level identifier generated for a top-level
// Data/Actions/Events declaration named name, escaping the rare case
// where a mission author's DSL identifier collides with a Go keyword.
func varName(name string) string {
	if token.Lookup(name).IsKeyword() {
		return name + "_"
	}
	return name
}
