package parser

import (
	"github.com/alecthomas/participle/v2"
	"github.com/alecthomas/participle/v2/lexer"
)

type Ast struct {
	Role     *RoleStanza     `parser:"@@?"`
	Override *OverrideStanza `parser:"@@?"`
	Import   *ImportStanza   `parser:"@@?"`
	Data     *DataStanza     `parser:"@@?"`
	Actions  *ActionsStanza  `parser:"@@?"`
	Events   *EventsStanza   `parser:"@@?"`
	Mission  *MissionStanza  `parser:"@@?"`
}

type RoleStanza struct {
	Name string `parser:"\"Role\" @Ident \":\""`
}

// OverrideStanza lists local filesystem directories that the compiler adds
// to its scratch Go workspace (see newWorkspace in compiler.go), so that any
// Import whose module path matches one of these directories' own go.mod
// resolves to the local source instead of being fetched.
type OverrideStanza struct {
	Paths []*OverrideSpec `parser:"\"Override\" \":\" @@*"`
}

// OverrideSpec is a single local filesystem path, written as a quoted
// string since filesystem paths commonly start with characters ('.', '/',
// '~') that an unquoted token can't unambiguously begin with.
type OverrideSpec struct {
	Pos  lexer.Position
	Path string `parser:"@String"`
}

type ImportStanza struct {
	Imports []*ImportSpec `parser:"\"Import\" \":\" @@*"`
}

// ImportSpec is a single imported package path, optionally preceded by an
// alias Ident used to qualify types from that package and optionally followed
// by a version (e.g. "basesdk "github.com/cmusatyalab/steeleagle/sdk" v1.2.3").
// When Alias is empty, the package's own name is used as the qualifier. When no
// version is provided the latest version is fetched.
type ImportSpec struct {
	Pos     lexer.Position
	Alias   string `parser:"(@Ident)?"`
	Path    string `parser:"@String"`
	Version string `parser:"@Version?"`
}

type DataStanza struct {
	Decls []*Decl `parser:"\"Data\" \":\" @@*"`
}

type ActionsStanza struct {
	Decls []*Decl `parser:"\"Actions\" \":\" @@*"`
}

type EventsStanza struct {
	Decls []*Decl `parser:"\"Events\" \":\" @@*"`
}

// TypeName is a dot-qualified type reference such as "actions.TakeOff". It
// contains only letters, digits and underscores separated by single dots,
// and cannot start or end with a dot (no path separators allowed).
type TypeName string

type Decl struct {
	Pos   lexer.Position
	Type  TypeName `parser:"@(Ident | QualIdent)"`
	Name  string   `parser:"@Ident"`
	Attrs []*Attr  `parser:"\"(\" (@@ (\",\" @@)*)? \")\""`
}

type Attr struct {
	Key   string `parser:"@Ident \"=\""`
	Value *Value `parser:"@@"`
}

type Value struct {
	Pos    lexer.Position
	Float  *float64    `parser:"@Float"`
	Int    *int64      `parser:"| @Int"`
	String *string     `parser:"| @String"`
	Array  *ArrayValue `parser:"| @@"`
	Inline *InlineCtor `parser:"| @@"`
	Ident  *string     `parser:"| @Ident"`
}

type ArrayValue struct {
	Elems []*Value `parser:"\"[\" (@@ (\",\" @@)*)? \"]\""`
}

// InlineCtor is a keyword-argument constructor call used as a value.
type InlineCtor struct {
	Type TypeName `parser:"@(Ident | QualIdent)"`
	Args []*Attr  `parser:"\"(\" (@@ (\",\" @@)*)? \")\""`
}

type MissionStanza struct {
	Pos    lexer.Position
	Start  string         `parser:"\"Mission\" \":\" \"Start\" @Ident"`
	Blocks []*DuringBlock `parser:"@@*"`
}

type DuringBlock struct {
	Pos    lexer.Position
	Action string  `parser:"\"During\" @Ident \":\""`
	Rules  []*Rule `parser:"@@*"`
}

type Rule struct {
	Pos   lexer.Position
	Event string `parser:"@Ident \"->\""`
	Next  string `parser:"@Ident"`
}

// unquoteString strips the surrounding quotes from a raw String-token
// capture (e.g. `'foo'` or `"foo"`).
func unquoteString(raw string) string {
	if len(raw) >= 2 {
		return raw[1 : len(raw)-1]
	}
	return raw
}

func (v *Value) StringValue() (s string, ok bool) {
	if v.String == nil {
		return "", false
	}
	return unquoteString(*v.String), true
}

var dslLexer = lexer.MustSimple([]lexer.SimpleRule{
	{Name: "Comment", Pattern: `#[^\n]*`},
	{Name: "Arrow", Pattern: `->`},
	{Name: "Float", Pattern: `-?\d+(?:\.\d+)?`},
	{Name: "Int", Pattern: `-?\d+`},
	{Name: "String", Pattern: `'[^']*'|"[^"]*"`},
	{Name: "QualIdent", Pattern: `[a-zA-Z][a-zA-Z_\d]*(?:\.[a-zA-Z][a-zA-Z_\d]*)+`},
	{Name: "Version", Pattern: `v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?`},
	{Name: "Ident", Pattern: `[a-zA-Z][a-zA-Z_\d]*`},
	{Name: "Punct", Pattern: `[:(),=\[\]]`},
	{Name: "Whitespace", Pattern: `[ \t\r\n]+`},
})

var dslParser = participle.MustBuild[Ast](
	participle.Lexer(dslLexer),
	participle.Elide("Whitespace", "Comment"),
	participle.UseLookahead(2),
)
