package parser

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"

	"github.com/alecthomas/participle/v2/lexer"
)

// TestParseAllStanzasEndToEnd checks that a mission file exercising every
// stanza type is parsed into an *Ast whose structure matches the source,
// including Import path unquoting.
func TestParseAllStanzasEndToEnd(t *testing.T) {
	src := `
Role Leader:

Modules:
	"github.com/cmusatyalab/steeleagle/sdk" v1.2.3 => "../sdk"

Imports:
	basesdk "github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/actions"

Data:
	types.Waypoint w1(lat=1.5, label="home")

Actions:
	actions.TakeOff takeoff(altitude=2.5)
	actions.Land land()

Events:
	events.Seen seen(target="person")

Mission:
Start takeoff
During takeoff:
	done -> land
During land:
	seen -> takeoff
`
	ast := mustParse(t, src)

	if ast.Role == nil || ast.Role.Name != "Leader" {
		t.Fatalf("Role = %+v, want Name %q", ast.Role, "Leader")
	}

	if len(ast.Modules.Modules) != 1 {
		t.Fatalf("Modules.Modules = %+v, want 1 entry", ast.Modules.Modules)
	}
	mod := ast.Modules.Modules[0]
	if mod.Path != "github.com/cmusatyalab/steeleagle/sdk" || mod.Version != "v1.2.3" || mod.Override != "../sdk" {
		t.Errorf("Modules[0] = %+v, want unquoted path, version v1.2.3, unquoted override ../sdk", mod)
	}

	if len(ast.Imports.Imports) != 2 {
		t.Fatalf("Imports.Imports = %+v, want 2 entries", ast.Imports.Imports)
	}
	base := ast.Imports.Imports[0]
	if base.Alias != "basesdk" || base.Path != "github.com/cmusatyalab/steeleagle/sdk" {
		t.Errorf("Imports[0] = %+v, want alias basesdk, unquoted path", base)
	}
	actionsImp := ast.Imports.Imports[1]
	if actionsImp.Alias != "" {
		t.Errorf("Imports[1] = %+v, want empty Alias", actionsImp)
	}

	if len(ast.Data.Decls) != 1 {
		t.Fatalf("Data.Decls = %+v, want exactly 1", ast.Data.Decls)
	}
	w1 := ast.Data.Decls[0]
	if w1.Type != "types.Waypoint" || w1.Name != "w1" {
		t.Errorf("Data decl = %+v, want types.Waypoint w1", w1)
	}

	if len(ast.Actions.Decls) != 2 || ast.Actions.Decls[0].Name != "takeoff" || ast.Actions.Decls[1].Name != "land" {
		t.Fatalf("Actions.Decls = %+v, want [takeoff, land]", ast.Actions.Decls)
	}
	if len(ast.Events.Decls) != 1 || ast.Events.Decls[0].Name != "seen" {
		t.Fatalf("Events.Decls = %+v, want [seen]", ast.Events.Decls)
	}

	if ast.Mission.Start != "takeoff" {
		t.Fatalf("Mission.Start = %q, want %q", ast.Mission.Start, "takeoff")
	}
	if len(ast.Mission.Blocks) != 2 {
		t.Fatalf("Mission.Blocks = %+v, want exactly 2", ast.Mission.Blocks)
	}
	takeoffBlock := ast.Mission.Blocks[0]
	if takeoffBlock.Action != "takeoff" || len(takeoffBlock.Rules) != 1 ||
		takeoffBlock.Rules[0].Event != "done" || takeoffBlock.Rules[0].Next != "land" {
		t.Errorf("Blocks[0] = %+v, want During takeoff: done -> land", takeoffBlock)
	}
}

// TestParseEmptyInputReturnsEmptyAst checks that a source with no stanzas
// at all parses successfully, since every top-level stanza is optional.
// Every stanza is present but empty.
func TestParseEmptyInputReturnsEmptyAst(t *testing.T) {
	assertEmptyStanzas(t, mustParse(t, ""))
}

// TestParseEmptyStanzaHeadersReturnEmptyLists checks that list stanzas
// written as a bare header with no entries get empty, non-nil lists, the
// same as when the stanza is left out.
func TestParseEmptyStanzaHeadersReturnEmptyLists(t *testing.T) {
	assertEmptyStanzas(t, mustParse(t, "Modules:\nImports:\nData:\nActions:\nEvents:\n"))
}

// TestParseModuleOmittedBeforeImport checks that the Modules stanza can be
// left out of a mission that has an Imports stanza, leaving Modules empty
// but non-nil.
func TestParseModuleOmittedBeforeImport(t *testing.T) {
	ast := mustParse(t, "Role Leader:\nImports:\n\t\"example.com/sdk\"\n")
	if ast.Modules == nil || ast.Modules.Modules == nil || len(ast.Modules.Modules) != 0 {
		t.Errorf("Modules = %+v, want present with an empty, non-nil Modules", ast.Modules)
	}
	if len(ast.Imports.Imports) != 1 || ast.Imports.Imports[0].Path != "example.com/sdk" {
		t.Errorf("Imports = %+v, want example.com/sdk", ast.Imports.Imports)
	}
}

// assertEmptyStanzas checks that every stanza of ast is present but empty,
// with list stanzas holding empty, non-nil lists.
func assertEmptyStanzas(t *testing.T, ast *Ast) {
	t.Helper()
	if ast.Role == nil || ast.Role.Name != "" {
		t.Errorf("Role = %+v, want present with an empty Name", ast.Role)
	}
	if ast.Modules == nil || ast.Modules.Modules == nil || len(ast.Modules.Modules) != 0 {
		t.Errorf("Modules = %+v, want present with empty, non-nil Modules", ast.Modules)
	}
	if ast.Imports == nil || ast.Imports.Imports == nil || len(ast.Imports.Imports) != 0 {
		t.Errorf("Imports = %+v, want present with empty, non-nil Imports", ast.Imports)
	}
	if ast.Mission == nil || ast.Mission.Start != "" || len(ast.Mission.Blocks) != 0 {
		t.Errorf("Mission = %+v, want present with no Start or Blocks", ast.Mission)
	}
	for name, decls := range map[string][]*Decl{"Data": ast.Data.Decls, "Actions": ast.Actions.Decls, "Events": ast.Events.Decls} {
		if decls == nil || len(decls) != 0 {
			t.Errorf("%s.Decls = %#v, want empty and non-nil", name, decls)
		}
	}
}

// TestParseSkipsAbsentLeadingStanzas checks that a mission omitting every
// stanza before Actions still parses, since each stanza is independently
// optional.
func TestParseSkipsAbsentLeadingStanzas(t *testing.T) {
	src := "Actions:\n\tactions.TakeOff takeoff()\nMission:\nStart takeoff\n"
	ast := mustParse(t, src)
	if ast.Role == nil || ast.Role.Name != "" || ast.Imports == nil || len(ast.Imports.Imports) != 0 {
		t.Errorf("ast = %+v, want Role and Import present but empty", ast)
	}
	if ast.Data == nil || len(ast.Data.Decls) != 0 || ast.Events == nil || len(ast.Events.Decls) != 0 {
		t.Errorf("ast = %+v, want Data and Events present with empty Decls", ast)
	}
	if ast.Actions == nil || ast.Mission == nil {
		t.Fatalf("ast = %+v, want Actions and Mission populated", ast)
	}
}

// TestParseStanzaOutOfOrderErrors checks that the stanzas must appear in
// their declared order (Role, Module, Import, Data, Actions, Events,
// Mission): a stanza written before one that should precede it leaves the
// later stanza unconsumed and is reported as a parse error rather than
// silently reordered.
func TestParseStanzaOutOfOrderErrors(t *testing.T) {
	cases := map[string]string{
		"mission before actions": "Mission:\nStart takeoff\nActions:\n\tactions.TakeOff takeoff()\n",
		"import before module":   "Imports:\n\t\"example.com/sdk\"\nModules:\n\t\"example.com/sdk\"\n",
	}
	for name, src := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := parse("test.dsl", strings.NewReader(src)); err == nil {
				t.Fatal("Parse() error = nil, want an error for out-of-order stanzas")
			}
		})
	}
}

// TestParseImportOptionalAlias checks ImportSpec with and without its
// optional leading Alias, and that a trailing version is rejected.
func TestParseImportOptionalAlias(t *testing.T) {
	cases := []struct {
		name      string
		line      string
		wantAlias string
	}{
		{"alias", `sdk "example.com/sdk"`, "sdk"},
		{"no alias", `"example.com/sdk"`, ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ast := mustParse(t, "Imports:\n\t"+c.line+"\n")
			if len(ast.Imports.Imports) != 1 {
				t.Fatalf("Imports = %+v, want exactly 1", ast.Imports.Imports)
			}
			imp := ast.Imports.Imports[0]
			if imp.Alias != c.wantAlias {
				t.Errorf("Alias = %q, want %q", imp.Alias, c.wantAlias)
			}
			if imp.Path != "example.com/sdk" {
				t.Errorf("Path = %q, want %q", imp.Path, "example.com/sdk")
			}
		})
	}
	if _, err := parse("test.dsl", strings.NewReader("Imports:\n\t\"example.com/sdk\" v1.2.3\n")); err == nil {
		t.Error("Parse() error = nil, want an error for a versioned Import")
	}
}

// TestParseModuleOptionalVersionAndOverride checks every combination of
// ModuleSpec's optional Version and Override, including several modules
// in one stanza (so an override is not confused with the next path).
func TestParseModuleOptionalVersionAndOverride(t *testing.T) {
	cases := []struct {
		name         string
		line         string
		wantVersion  string
		wantOverride string
	}{
		{"version and override", `"example.com/sdk" v1.2.3 => "../sdk"`, "v1.2.3", "../sdk"},
		{"version only", `"example.com/sdk" v2.0.0`, "v2.0.0", ""},
		{"override only", `"example.com/sdk" => '/abs/sdk'`, "", "/abs/sdk"},
		{"neither", `"example.com/sdk"`, "", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ast := mustParse(t, "Modules:\n\t"+c.line+"\n\t\"example.com/other\"\n")
			if len(ast.Modules.Modules) != 2 {
				t.Fatalf("Modules = %+v, want exactly 2", ast.Modules.Modules)
			}
			mod := ast.Modules.Modules[0]
			if mod.Path != "example.com/sdk" {
				t.Errorf("Path = %q, want %q", mod.Path, "example.com/sdk")
			}
			if mod.Version != c.wantVersion {
				t.Errorf("Version = %q, want %q", mod.Version, c.wantVersion)
			}
			if mod.Override != c.wantOverride {
				t.Errorf("Override = %q, want %q", mod.Override, c.wantOverride)
			}
			if other := ast.Modules.Modules[1]; other.Path != "example.com/other" || other.Version != "" || other.Override != "" {
				t.Errorf("Modules[1] = %+v, want bare example.com/other", other)
			}
		})
	}
}

// TestParseValueKinds checks that each syntactic form of an attribute
// value is captured under the matching Value field, and that every other
// field of the union is left nil.
func TestParseValueKinds(t *testing.T) {
	cases := []struct {
		name  string
		value string
		check func(t *testing.T, v *Value)
	}{
		{"decimal", "2.5", func(t *testing.T, v *Value) {
			if v.Float == nil || *v.Float != 2.5 {
				t.Errorf("Float = %v, want 2.5", v.Float)
			}
		}},
		{"negative decimal", "-1.5", func(t *testing.T, v *Value) {
			if v.Float == nil || *v.Float != -1.5 {
				t.Errorf("Float = %v, want -1.5", v.Float)
			}
		}},
		{"integer", "5", func(t *testing.T, v *Value) {
			if v.Int == nil || *v.Int != 5 {
				t.Errorf("Int = %v, want 5", v.Int)
			}
			if v.Float != nil {
				t.Errorf("Float = %v, want nil", *v.Float)
			}
		}},
		{"negative integer", "-3", func(t *testing.T, v *Value) {
			if v.Int == nil || *v.Int != -3 {
				t.Errorf("Int = %v, want -3", v.Int)
			}
		}},
		{"double-quoted string", `"home"`, func(t *testing.T, v *Value) {
			s, ok := v.StringValue()
			if !ok || s != "home" {
				t.Errorf("StringValue() = (%q, %v), want (%q, true)", s, ok, "home")
			}
		}},
		{"single-quoted string", `'home'`, func(t *testing.T, v *Value) {
			s, ok := v.StringValue()
			if !ok || s != "home" {
				t.Errorf("StringValue() = (%q, %v), want (%q, true)", s, ok, "home")
			}
		}},
		{"bare ident", "Fast", func(t *testing.T, v *Value) {
			if v.Ident == nil || *v.Ident != "Fast" {
				t.Errorf("Ident = %v, want Fast", v.Ident)
			}
		}},
		{"qualified ident", "params.Poly", func(t *testing.T, v *Value) {
			if v.Ident == nil || *v.Ident != "params.Poly" {
				t.Errorf("Ident = %v, want params.Poly", v.Ident)
			}
		}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ast := mustParse(t, "Data:\n\ttypes.Waypoint w1(v="+c.value+")\n")
			c.check(t, ast.Data.Decls[0].Attrs[0].Value)
		})
	}
}

// TestParseFloatRequiresFractionalPart checks that dslLexer's Float rule
// only matches a decimal.
func TestParseFloatRequiresFractionalPart(t *testing.T) {
	ast := mustParse(t, "Data:\n\ttypes.Waypoint w1(count=5, ratio=5.0)\n")
	count := ast.Data.Decls[0].Attrs[0].Value
	if count.Float != nil {
		t.Errorf("count.Float = %v, want nil", *count.Float)
	}
	if count.Int == nil || *count.Int != 5 {
		t.Errorf("count.Int = %v, want 5", count.Int)
	}

	ratio := ast.Data.Decls[0].Attrs[1].Value
	if ratio.Int != nil {
		t.Errorf("ratio.Int = %v, want nil", *ratio.Int)
	}
	if ratio.Float == nil || *ratio.Float != 5.0 {
		t.Errorf("ratio.Float = %v, want 5.0", ratio.Float)
	}
}

// TestParseArrayValueNested checks that an array value collects every
// element in order, preserving each element's own kind.
func TestParseArrayValueNested(t *testing.T) {
	ast := mustParse(t, `Data:
	types.Waypoint w1(tags=[1, 2.5, "three"])
`)
	v := ast.Data.Decls[0].Attrs[0].Value
	if v.Array == nil {
		t.Fatalf("Array = nil, want a populated ArrayValue")
	}
	elems := v.Array.Elems
	if len(elems) != 3 {
		t.Fatalf("Elems = %+v, want 3 entries", elems)
	}
	if elems[0].Int == nil || *elems[0].Int != 1 {
		t.Errorf("Elems[0].Int = %v, want 1", elems[0].Int)
	}
	if elems[1].Float == nil || *elems[1].Float != 2.5 {
		t.Errorf("Elems[1].Float = %v, want 2.5", elems[1].Float)
	}
	if s, ok := elems[2].StringValue(); !ok || s != "three" {
		t.Errorf("Elems[2].StringValue() = (%q, %v), want (%q, true)", s, ok, "three")
	}
}

// TestParseInlineCtorNestedArgs checks that an inline constructor value
// captures its type name and its own keyword arguments, which may
// themselves be arbitrary Values (here, another nested inline ctor).
func TestParseInlineCtorNestedArgs(t *testing.T) {
	ast := mustParse(t, `Data:
	types.Waypoint w1(pose=types.Pose(pitch=0, roll=types.Nudge(deg=1)))
`)
	v := ast.Data.Decls[0].Attrs[0].Value
	if v.Inline == nil {
		t.Fatalf("Inline = nil, want a populated InlineCtor")
	}
	if v.Inline.Type != "types.Pose" {
		t.Errorf("Inline.Type = %q, want %q", v.Inline.Type, "types.Pose")
	}
	if len(v.Inline.Args) != 2 {
		t.Fatalf("Inline.Args = %+v, want 2 entries", v.Inline.Args)
	}
	roll := v.Inline.Args[1]
	if roll.Key != "roll" || roll.Value.Inline == nil || roll.Value.Inline.Type != "types.Nudge" {
		t.Errorf("Args[1] = %+v, want roll=types.Nudge(...)", roll)
	}
}

// TestParseDeclTypeAcceptsPlainAndQualifiedIdent checks that a Decl's Type
// accepts both an unqualified Ident and a dotted QualIdent.
func TestParseDeclTypeAcceptsPlainAndQualifiedIdent(t *testing.T) {
	ast := mustParse(t, "Actions:\n\tTakeOff a()\n\tactions.Land b()\n")
	decls := ast.Actions.Decls
	if len(decls) != 2 {
		t.Fatalf("Decls = %+v, want 2 entries", decls)
	}
	if decls[0].Type != "TakeOff" {
		t.Errorf("Decls[0].Type = %q, want %q", decls[0].Type, "TakeOff")
	}
	if decls[1].Type != "actions.Land" {
		t.Errorf("Decls[1].Type = %q, want %q", decls[1].Type, "actions.Land")
	}
}

// TestParseMissionMultipleBlocksAndRules checks that Mission collects
// every During block in order, each with its own ordered list of Rules.
func TestParseMissionMultipleBlocksAndRules(t *testing.T) {
	src := `Mission:
Start a
During a:
	x -> b
	y -> c
During b:
	z -> a
`
	ast := mustParse(t, src)
	if ast.Mission.Start != "a" {
		t.Fatalf("Start = %q, want %q", ast.Mission.Start, "a")
	}
	if len(ast.Mission.Blocks) != 2 {
		t.Fatalf("Blocks = %+v, want 2 entries", ast.Mission.Blocks)
	}
	first := ast.Mission.Blocks[0]
	if first.Action != "a" || len(first.Rules) != 2 {
		t.Fatalf("Blocks[0] = %+v, want During a with 2 rules", first)
	}
	if first.Rules[0].Event != "x" || first.Rules[0].Next != "b" {
		t.Errorf("Rules[0] = %+v, want x -> b", first.Rules[0])
	}
	if first.Rules[1].Event != "y" || first.Rules[1].Next != "c" {
		t.Errorf("Rules[1] = %+v, want y -> c", first.Rules[1])
	}
}

// TestParseCommentsAndBlankLinesIgnored checks that "#"-line comments and
// blank lines don't affect the parsed result, since the lexer elides both
// Comment and Whitespace tokens.
func TestParseCommentsAndBlankLinesIgnored(t *testing.T) {
	withComments := mustParse(t, `# top-level comment
Role Leader: # trailing comment

# another comment
`)
	withoutComments := mustParse(t, "Role Leader:\n")
	if withComments.Role.Name != withoutComments.Role.Name {
		t.Errorf("Role.Name = %q with comments, %q without", withComments.Role.Name, withoutComments.Role.Name)
	}
}

// TestParseSyntaxErrors checks that a handful of structurally invalid
// inputs are rejected with a non-nil error and a nil *Ast, instead of
// panicking or silently producing a partial result.
func TestParseSyntaxErrors(t *testing.T) {
	cases := map[string]string{
		"unclosed paren":          "Actions:\n\tactions.TakeOff a(\n",
		"decl missing parens":     "Actions:\n\tactions.TakeOff a\n",
		"stanza missing colon":    "Role Leader\n",
		"attr missing value":      "Actions:\n\tactions.TakeOff a(altitude=)\n",
		"rule missing arrow dst":  "Mission:\nStart a\nDuring a:\n\tdone ->\n",
		"module override no path": "Modules:\n\t\"example.com/sdk\" v1.2.3 =>\n",
		"module override ident":   "Modules:\n\t\"example.com/sdk\" => sdk\n",
		"module version first":    "Modules:\n\tv1.2.3 \"example.com/sdk\"\n",
		"module unquoted path":    "Modules:\n\texample.com/sdk\n",
		"module alias":            "Modules:\n\tsdk \"example.com/sdk\"\n",
	}
	for name, src := range cases {
		t.Run(name, func(t *testing.T) {
			ast, err := parse("test.dsl", strings.NewReader(src))
			if err == nil {
				t.Fatalf("Parse() error = nil, want an error; ast = %+v", ast)
			}
			if ast != nil {
				t.Errorf("ast = %+v, want nil on error", ast)
			}
		})
	}
}

// TestParseFromJsonAllStanzas checks that a JSON mission covering every
// stanza decodes into the same shape Parse would produce, including String
// values that StringValue unquotes and nested inline constructors.
func TestParseFromJsonAllStanzas(t *testing.T) {
	src := `{
		"Role": {"Name": "Leader"},
		"Modules": {"Modules": [{"Path": "github.com/cmusatyalab/steeleagle/sdk", "Version": "v1.2.3", "Override": "../sdk"}]},
		"Imports": {"Imports": [{"Alias": "basesdk", "Path": "github.com/cmusatyalab/steeleagle/sdk"}]},
		"Data": {"Decls": [{"Type": "types.Waypoint", "Name": "w1", "Attrs": [
			{"Key": "label", "Value": {"String": "home"}},
			{"Key": "pose", "Value": {"Inline": {"Type": "types.Pose", "Args": [
				{"Key": "tag", "Value": {"String": "p"}}]}}},
			{"Key": "xs", "Value": {"Array": {"Elems": [{"Int": 1}, {"String": "two"}]}}}
		]}]},
		"Actions": {"Decls": [{"Type": "actions.TakeOff", "Name": "takeoff", "Attrs": [
			{"Key": "altitude", "Value": {"Float": 2.5}}]}]},
		"Mission": {"Start": "takeoff", "Blocks": [{"Action": "takeoff", "Rules": [{"Event": "done", "Next": "takeoff"}]}]}
	}`
	ast, err := ParseFromJson([]byte(src))
	if err != nil {
		t.Fatalf("ParseFromJson() error = %v", err)
	}
	if ast.Role.Name != "Leader" || ast.Imports.Imports[0].Alias != "basesdk" {
		t.Errorf("header stanzas = %+v %+v", ast.Role, ast.Imports)
	}
	attrs := ast.Data.Decls[0].Attrs
	if s, ok := attrs[0].Value.StringValue(); !ok || s != "home" {
		t.Errorf("label StringValue() = (%q, %v), want (%q, true)", s, ok, "home")
	}
	inline := attrs[1].Value.Inline
	if inline == nil || inline.Type != "types.Pose" {
		t.Fatalf("pose Inline = %+v, want types.Pose", inline)
	}
	if s, ok := inline.Args[0].Value.StringValue(); !ok || s != "p" {
		t.Errorf("inline tag StringValue() = (%q, %v), want (%q, true)", s, ok, "p")
	}
	elems := attrs[2].Value.Array.Elems
	if *elems[0].Int != 1 {
		t.Errorf("Elems[0].Int = %d, want 1", *elems[0].Int)
	}
	if s, ok := elems[1].StringValue(); !ok || s != "two" {
		t.Errorf("Elems[1].StringValue() = (%q, %v), want (%q, true)", s, ok, "two")
	}
	if a := ast.Actions.Decls[0]; a.Type != "actions.TakeOff" || *a.Attrs[0].Value.Float != 2.5 {
		t.Errorf("Actions.Decls[0] = %+v", a)
	}
	if ast.Events == nil || len(ast.Events.Decls) != 0 {
		t.Errorf("Events = %+v, want present with empty Decls", ast.Events)
	}
	if ast.Mission.Start != "takeoff" || ast.Mission.Blocks[0].Rules[0].Next != "takeoff" {
		t.Errorf("Mission = %+v", ast.Mission)
	}
}

// TestParseFromJsonEmptyObject checks that "{}" decodes like an empty DSL
// file: every stanza present but empty.
func TestParseFromJsonEmptyObject(t *testing.T) {
	ast, err := ParseFromJson([]byte("{}"))
	if err != nil {
		t.Fatalf("ParseFromJson() error = %v", err)
	}
	assertEmptyStanzas(t, ast)
}

// TestParseFromJsonEmptyStanzaObjects checks that list stanzas given as
// empty objects or with null lists get empty, non-nil lists.
func TestParseFromJsonEmptyStanzaObjects(t *testing.T) {
	for name, src := range map[string]string{
		"empty objects": `{"Modules": {}, "Imports": {}, "Data": {}, "Actions": {}, "Events": {}}`,
		"null lists":    `{"Modules": {"Modules": null}, "Imports": {"Imports": null}, "Data": {"Decls": null}, "Actions": {"Decls": null}, "Events": {"Decls": null}}`,
		"null stanzas":  `{"Modules": null, "Imports": null, "Data": null, "Actions": null, "Events": null}`,
	} {
		t.Run(name, func(t *testing.T) {
			ast, err := ParseFromJson([]byte(src))
			if err != nil {
				t.Fatalf("ParseFromJson() error = %v", err)
			}
			assertEmptyStanzas(t, ast)
		})
	}
}

// TestParseFromJsonErrors checks that malformed input is rejected.
func TestParseFromJsonErrors(t *testing.T) {
	for name, src := range map[string]string{
		"empty input":          ``,
		"syntax":               `{"Role":`,
		"top-level array":      `[]`,
		"unknown field":        `{"Bogus": 1}`,
		"nested unknown":       `{"Role": {"Name": "L", "Bogus": 1}}`,
		"trailing data":        `{} {}`,
		"wrong type":           `{"Role": {"Name": 5}}`,
		"float into int":       `{"Data": {"Decls": [{"Type": "T", "Name": "n", "Attrs": [{"Key": "k", "Value": {"Int": 1.5}}]}]}}`,
		"null decl":            `{"Actions": {"Decls": [null]}}`,
		"null attr":            `{"Actions": {"Decls": [{"Type": "T", "Name": "n", "Attrs": [null]}]}}`,
		"missing value":        `{"Actions": {"Decls": [{"Type": "T", "Name": "n", "Attrs": [{"Key": "k"}]}]}}`,
		"null array element":   `{"Data": {"Decls": [{"Type": "T", "Name": "n", "Attrs": [{"Key": "k", "Value": {"Array": {"Elems": [null]}}}]}]}}`,
		"inline missing value": `{"Data": {"Decls": [{"Type": "T", "Name": "n", "Attrs": [{"Key": "k", "Value": {"Inline": {"Type": "U", "Args": [{"Key": "a"}]}}}]}]}}`,
	} {
		if _, err := ParseFromJson([]byte(src)); err == nil {
			t.Errorf("%s: ParseFromJson() error = nil, want an error", name)
		}
	}
}

// clearPositions zeroes every lexer.Position reachable from v so that ASTs
// built by Parse (which records source positions) and ParseFromJson (which
// does not) can be compared structurally.
func clearPositions(v reflect.Value) {
	switch v.Kind() {
	case reflect.Pointer:
		if !v.IsNil() {
			clearPositions(v.Elem())
		}
	case reflect.Slice:
		for i := 0; i < v.Len(); i++ {
			clearPositions(v.Index(i))
		}
	case reflect.Struct:
		if v.Type() == reflect.TypeOf(lexer.Position{}) {
			v.Set(reflect.Zero(v.Type()))
			return
		}
		for i := 0; i < v.NumField(); i++ {
			clearPositions(v.Field(i))
		}
	}
}

// TestParseFromJsonMatchesParse checks that a mission written in JSON
// decodes to exactly the same AST (ignoring source positions) as the same
// mission written in the DSL, covering every stanza and every Value kind.
func TestParseFromJsonMatchesParse(t *testing.T) {
	dsl := `
Role Leader:

Modules:
	"github.com/cmusatyalab/steeleagle/sdk" v1.2.3 => "../sdk"
	"example.com/other"

Imports:
	basesdk "github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/datatypes"

Data:
	types.Waypoint w1(lat=1.5, count=3, label="home", mode=Fast, frame=enums.Body, xs=[1, 2.5, "three"], empty=[])

Actions:
	actions.SetVelocity climb(Velocity=types.Velocity(XVel=1.5, YVel=0.0, ZVel=-0.5, AngularVel=0.0))
	actions.Land land()

Events:
	events.Seen seen(target="person")

Mission:
Start climb
During climb:
	seen -> land
	done -> land
During land:
`
	js := `{
		"Role": {"Name": "Leader"},
		"Modules": {"Modules": [
			{"Path": "github.com/cmusatyalab/steeleagle/sdk", "Version": "v1.2.3", "Override": "../sdk"},
			{"Path": "example.com/other"}
		]},
		"Imports": {"Imports": [
			{"Alias": "basesdk", "Path": "github.com/cmusatyalab/steeleagle/sdk"},
			{"Path": "github.com/cmusatyalab/steeleagle/sdk/dsl/datatypes"}
		]},
		"Data": {"Decls": [{"Type": "types.Waypoint", "Name": "w1", "Attrs": [
			{"Key": "lat", "Value": {"Float": 1.5}},
			{"Key": "count", "Value": {"Int": 3}},
			{"Key": "label", "Value": {"String": "home"}},
			{"Key": "mode", "Value": {"Ident": "Fast"}},
			{"Key": "frame", "Value": {"Ident": "enums.Body"}},
			{"Key": "xs", "Value": {"Array": {"Elems": [{"Int": 1}, {"Float": 2.5}, {"String": "three"}]}}},
			{"Key": "empty", "Value": {"Array": {}}}
		]}]},
		"Actions": {"Decls": [
			{"Type": "actions.SetVelocity", "Name": "climb", "Attrs": [
				{"Key": "Velocity", "Value": {"Inline": {"Type": "types.Velocity", "Args": [
					{"Key": "XVel", "Value": {"Float": 1.5}},
					{"Key": "YVel", "Value": {"Float": 0.0}},
					{"Key": "ZVel", "Value": {"Float": -0.5}},
					{"Key": "AngularVel", "Value": {"Float": 0.0}}
				]}}}
			]},
			{"Type": "actions.Land", "Name": "land"}
		]},
		"Events": {"Decls": [{"Type": "events.Seen", "Name": "seen", "Attrs": [
			{"Key": "target", "Value": {"String": "person"}}
		]}]},
		"Mission": {"Start": "climb", "Blocks": [
			{"Action": "climb", "Rules": [{"Event": "seen", "Next": "land"}, {"Event": "done", "Next": "land"}]},
			{"Action": "land"}
		]}
	}`
	fromDSL := mustParse(t, dsl)
	fromJson, err := ParseFromJson([]byte(js))
	if err != nil {
		t.Fatalf("ParseFromJson() error = %v", err)
	}
	clearPositions(reflect.ValueOf(fromDSL))
	clearPositions(reflect.ValueOf(fromJson))
	if !reflect.DeepEqual(fromDSL, fromJson) {
		want, _ := json.MarshalIndent(fromDSL, "", "  ")
		got, _ := json.MarshalIndent(fromJson, "", "  ")
		t.Errorf("ParseFromJson() AST differs from Parse()\nParse:\n%s\nParseFromJson:\n%s", want, got)
	}
}

// TestParseFromJsonKeysCaseInsensitive checks that JSON structure keys
// match the Ast field names regardless of case, while attribute Keys (which
// name Go struct fields) are kept verbatim.
func TestParseFromJsonKeysCaseInsensitive(t *testing.T) {
	src := `{"actions": {"decls": [{"type": "actions.TakeOff", "name": "takeoff",
		"attrs": [{"key": "Altitude", "value": {"float": 2.5}}]}]}}`
	ast, err := ParseFromJson([]byte(src))
	if err != nil {
		t.Fatalf("ParseFromJson() error = %v", err)
	}
	d := ast.Actions.Decls[0]
	if d.Name != "takeoff" || d.Attrs[0].Key != "Altitude" || *d.Attrs[0].Value.Float != 2.5 {
		t.Errorf("Decls[0] = %+v, want takeoff(Altitude=2.5)", d)
	}
}

// TestParseFromJsonNullStanzasFilled checks that explicitly null Data,
// Actions and Events stanzas are treated the same as absent ones.
func TestParseFromJsonNullStanzasFilled(t *testing.T) {
	ast, err := ParseFromJson([]byte(`{"Data": null, "Actions": null, "Events": null}`))
	if err != nil {
		t.Fatalf("ParseFromJson() error = %v", err)
	}
	if ast.Data == nil || ast.Actions == nil || ast.Events == nil {
		t.Fatalf("ast = %+v, want Data, Actions and Events present", ast)
	}
	if len(ast.Data.Decls) != 0 || len(ast.Actions.Decls) != 0 || len(ast.Events.Decls) != 0 {
		t.Errorf("ast = %+v, want empty Decls", ast)
	}
}

// TestParseFromJsonStringValues checks that String values round-trip
// through StringValue unchanged, including empty strings and strings
// containing quote characters.
func TestParseFromJsonStringValues(t *testing.T) {
	for _, want := range []string{"", "home", `say "hi"`, "it's", "a\nb"} {
		attr, _ := json.Marshal(map[string]any{"Key": "k", "Value": map[string]string{"String": want}})
		src := `{"Data": {"Decls": [{"Type": "T", "Name": "n", "Attrs": [` + string(attr) + `]}]}}`
		ast, err := ParseFromJson([]byte(src))
		if err != nil {
			t.Fatalf("ParseFromJson(%q) error = %v", want, err)
		}
		if got, ok := ast.Data.Decls[0].Attrs[0].Value.StringValue(); !ok || got != want {
			t.Errorf("StringValue() = (%q, %v), want (%q, true)", got, ok, want)
		}
	}
}

// TestParseFromJsonPathsNotUnquoted checks that Import paths are taken
// verbatim from JSON rather than having their first and last characters
// stripped as Parse does for raw String tokens.
func TestParseFromJsonPathsNotUnquoted(t *testing.T) {
	src := `{"Imports": {"Imports": [{"Path": "example.com/pkg"}]}}`
	ast, err := ParseFromJson([]byte(src))
	if err != nil {
		t.Fatalf("ParseFromJson() error = %v", err)
	}
	if got := ast.Imports.Imports[0].Path; got != "example.com/pkg" {
		t.Errorf("Import path = %q, want %q", got, "example.com/pkg")
	}
}

// TestParseFromSource checks that a mission is parsed from source text,
// and that syntax errors carry a line but no file name.
func TestParseFromSource(t *testing.T) {
	ast, err := ParseFromSource([]byte("Imports:\n\t\"example.com/sdk\"\nMission:\nStart takeoff\n"))
	if err != nil {
		t.Fatalf("ParseFromSource() error = %v", err)
	}
	if ast.Mission.Start != "takeoff" || len(ast.Imports.Imports) != 1 || ast.Imports.Imports[0].Path != "example.com/sdk" {
		t.Errorf("ast = %+v %+v, want example.com/sdk imported and Start takeoff", ast.Imports, ast.Mission)
	}

	_, err = ParseFromSource([]byte("Mission:\nStart\n"))
	if err == nil {
		t.Fatal("ParseFromSource(syntax error) error = nil, want one")
	}
	if msg := err.Error(); !strings.HasPrefix(msg, "3:") {
		t.Errorf("error = %q, want it positioned at line 3 with no file name", msg)
	}
}
