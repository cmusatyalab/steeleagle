package main

import (
	"io"

	"github.com/alecthomas/participle/v2"
	"github.com/alecthomas/participle/v2/lexer"
)

type Ast struct {
	Role    *RoleStanza    `parser:"@@?"`
	Import  *ImportStanza  `parser:"@@?"`
	Data    *DataStanza    `parser:"@@?"`
	Actions *ActionsStanza `parser:"@@?"`
	Events  *EventsStanza  `parser:"@@?"`
	Mission *MissionStanza `parser:"@@?"`
}

type RoleStanza struct {
	Name string `parser:"\"Role\" @Ident \":\""`
}

type ImportStanza struct {
	Imports []*ImportSpec `parser:"\"Import\" \":\" @@*"`
}

// ImportSpec is a single imported package path, optionally preceded by an
// alias Ident used to qualify types from that package (e.g. "basesdk
// github.com/cmusatyalab/steeleagle/sdk"). When Alias is empty, the
// package's own name is used as the qualifier.
type ImportSpec struct {
	Pos   lexer.Position
	Alias string `parser:"(@Ident)?"`
	Path  string `parser:"@Path"`
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
	Pos     lexer.Position
	Float   *float64    `parser:"@Float"`
	Int     *int64      `parser:"| @Int"`
	String  *string     `parser:"| @String"`
	Array   *ArrayValue `parser:"| @@"`
	Inline  *InlineCtor `parser:"| @@"`
	GeoJson *string     `parser:"| @GeoJsonIdent"`
	Ident   *string     `parser:"| @Ident"`
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

func (v *Value) StringValue() (s string, ok bool) {
	if v.String == nil {
		return "", false
	}
	raw := *v.String
	if len(raw) >= 2 {
		return raw[1 : len(raw)-1], true
	}
	return raw, true
}

var dslLexer = lexer.MustSimple([]lexer.SimpleRule{
	{Name: "Comment", Pattern: `#[^\n]*`},
	{Name: "Path", Pattern: `[a-zA-Z][a-zA-Z_\d]*(?:\.[a-zA-Z_\d-]+)*(?:/[a-zA-Z_\d.-]+)+`},
	{Name: "Arrow", Pattern: `->`},
	{Name: "Float", Pattern: `-?\d+(?:\.\d+)?`},
	{Name: "Int", Pattern: `-?\d+`},
	{Name: "String", Pattern: `'[^']*'|"[^"]*"`},
	{Name: "QualIdent", Pattern: `[a-zA-Z][a-zA-Z_\d]*(?:\.[a-zA-Z][a-zA-Z_\d]*)+`},
	{Name: "GeoJsonIdent", Pattern: `geojson:[a-zA-Z][a-zA-Z_\d]*`},
	{Name: "Ident", Pattern: `[a-zA-Z][a-zA-Z_\d]*`},
	{Name: "Punct", Pattern: `[:(),=\[\]]`},
	{Name: "Whitespace", Pattern: `[ \t\r\n]+`},
})

var dslParser = participle.MustBuild[Ast](
	participle.Lexer(dslLexer),
	participle.Elide("Whitespace", "Comment"),
	participle.UseLookahead(2),
)

func Parse(filename string, r io.Reader) (*Ast, error) {
	return dslParser.Parse(filename, r)
}
