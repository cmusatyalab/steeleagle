package parser

import (
	"strings"
	"testing"
)

// TestParseAllStanzasEndToEnd checks that a mission file exercising every
// stanza type is parsed into an *Ast whose structure matches the source,
// including Override/Import path unquoting.
func TestParseAllStanzasEndToEnd(t *testing.T) {
	src := `
Role Leader:

Override:
	'../local/sdk'

Import:
	basesdk "github.com/cmusatyalab/steeleagle/sdk" v1.2.3
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

	if len(ast.Override.Paths) != 1 || ast.Override.Paths[0].Path != "../local/sdk" {
		t.Fatalf("Override.Paths = %+v, want [../local/sdk]", ast.Override.Paths)
	}

	if len(ast.Import.Imports) != 2 {
		t.Fatalf("Import.Imports = %+v, want 2 entries", ast.Import.Imports)
	}
	base := ast.Import.Imports[0]
	if base.Alias != "basesdk" || base.Path != "github.com/cmusatyalab/steeleagle/sdk" || base.Version != "v1.2.3" {
		t.Errorf("Imports[0] = %+v, want alias basesdk, unquoted path, version v1.2.3", base)
	}
	actionsImp := ast.Import.Imports[1]
	if actionsImp.Alias != "" || actionsImp.Version != "" {
		t.Errorf("Imports[1] = %+v, want empty Alias and Version", actionsImp)
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
// at all parses successfully into an *Ast with every field nil, since
// every top-level stanza is optional.
func TestParseEmptyInputReturnsEmptyAst(t *testing.T) {
	ast := mustParse(t, "")
	if ast.Role != nil || ast.Override != nil || ast.Import != nil || ast.Data != nil ||
		ast.Actions != nil || ast.Events != nil || ast.Mission != nil {
		t.Errorf("ast = %+v, want every field nil", ast)
	}
}

// TestParseSkipsAbsentLeadingStanzas checks that a mission omitting every
// stanza before Actions still parses, since each stanza is independently
// optional.
func TestParseSkipsAbsentLeadingStanzas(t *testing.T) {
	src := "Actions:\n\tactions.TakeOff takeoff()\nMission:\nStart takeoff\n"
	ast := mustParse(t, src)
	if ast.Role != nil || ast.Override != nil || ast.Import != nil || ast.Data != nil || ast.Events != nil {
		t.Errorf("ast = %+v, want only Actions and Mission populated", ast)
	}
	if ast.Actions == nil || ast.Mission == nil {
		t.Fatalf("ast = %+v, want Actions and Mission populated", ast)
	}
}

// TestParseStanzaOutOfOrderErrors checks that the stanzas must appear in
// their declared order (Role, Override, Import, Data, Actions, Events,
// Mission): a Mission stanza written before Actions leaves "Actions:"
// unconsumed and is reported as a parse error rather than silently
// reordered.
func TestParseStanzaOutOfOrderErrors(t *testing.T) {
	src := "Mission:\nStart takeoff\nActions:\n\tactions.TakeOff takeoff()\n"
	if _, err := Parse("test.dsl", strings.NewReader(src)); err == nil {
		t.Fatal("Parse() error = nil, want an error for out-of-order stanzas")
	}
}

// TestParseOverridePathsUnquoteSingleAndDoubleQuotes checks that Override
// paths written with either quote style come back with their quotes
// stripped.
func TestParseOverridePathsUnquoteSingleAndDoubleQuotes(t *testing.T) {
	src := "Override:\n\t'../single'\n\t\"../double\"\n"
	ast := mustParse(t, src)
	if len(ast.Override.Paths) != 2 {
		t.Fatalf("Override.Paths = %+v, want 2 entries", ast.Override.Paths)
	}
	if got := ast.Override.Paths[0].Path; got != "../single" {
		t.Errorf("Paths[0].Path = %q, want %q", got, "../single")
	}
	if got := ast.Override.Paths[1].Path; got != "../double" {
		t.Errorf("Paths[1].Path = %q, want %q", got, "../double")
	}
}

// TestParseImportOptionalAliasAndVersion checks every combination of
// ImportSpec's optional leading Alias and trailing Version.
func TestParseImportOptionalAliasAndVersion(t *testing.T) {
	cases := []struct {
		name        string
		line        string
		wantAlias   string
		wantVersion string
	}{
		{"alias and version", `sdk "example.com/sdk" v1.2.3`, "sdk", "v1.2.3"},
		{"alias only", `sdk "example.com/sdk"`, "sdk", ""},
		{"version only", `"example.com/sdk" v2.0.0`, "", "v2.0.0"},
		{"neither", `"example.com/sdk"`, "", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ast := mustParse(t, "Import:\n\t"+c.line+"\n")
			if len(ast.Import.Imports) != 1 {
				t.Fatalf("Imports = %+v, want exactly 1", ast.Import.Imports)
			}
			imp := ast.Import.Imports[0]
			if imp.Alias != c.wantAlias {
				t.Errorf("Alias = %q, want %q", imp.Alias, c.wantAlias)
			}
			if imp.Path != "example.com/sdk" {
				t.Errorf("Path = %q, want %q", imp.Path, "example.com/sdk")
			}
			if imp.Version != c.wantVersion {
				t.Errorf("Version = %q, want %q", imp.Version, c.wantVersion)
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
		"unclosed paren":         "Actions:\n\tactions.TakeOff a(\n",
		"decl missing parens":    "Actions:\n\tactions.TakeOff a\n",
		"stanza missing colon":   "Role Leader\n",
		"attr missing value":     "Actions:\n\tactions.TakeOff a(altitude=)\n",
		"rule missing arrow dst": "Mission:\nStart a\nDuring a:\n\tdone ->\n",
	}
	for name, src := range cases {
		t.Run(name, func(t *testing.T) {
			ast, err := Parse("test.dsl", strings.NewReader(src))
			if err == nil {
				t.Fatalf("Parse() error = nil, want an error; ast = %+v", ast)
			}
			if ast != nil {
				t.Errorf("ast = %+v, want nil on error", ast)
			}
		})
	}
}
