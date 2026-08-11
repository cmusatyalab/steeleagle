package compiler

import (
	"io"

	"github.com/alecthomas/participle/v2"
	"github.com/alecthomas/participle/v2/lexer"
)

type File struct {
	Role    *RoleStanza    `parser:"@@?"`
	Imports *ImportStanza  `parser:"@@?"`
	Data    *DataStanza    `parser:"@@?"`
	Actions *ActionsStanza `parser:"@@?"`
	Events  *EventsStanza  `parser:"@@?"`
	Mission *MissionStanza `parser:"@@?"`
}

type RoleStanza struct {
	Name string `parser:"\"Role\" @Ident \":\""`
}

type ImportStanza struct {
	Paths []string `parser:"\"Import\" \":\" @Path*"`
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

type Decl struct {
	Pos   lexer.Position
	Type  string  `parser:"@Ident"`
	Name  string  `parser:"@Ident"`
	Attrs []*Attr `parser:"\"(\" (@@ (\",\" @@)*)? \")\""`
}

type Attr struct {
	Key   string `parser:"@Ident \"=\""`
	Value *Value `parser:"@@"`
}

type Value struct {
	Pos    lexer.Position
	Float  *float64    `parser:"@Float"`
	Int    *int64      `parser:"@Int"`
	String *string     `parser:"| @String"`
	Array  *ArrayValue `parser:"| @@"`
	Inline *InlineCtor `parser:"| @@"`
	Ident  *string     `parser:"| @Ident"`
}

type ArrayValue struct {
	Elems []*Value `parser:"\"[\" (@@ (\",\" @@)*)? \"]\""`
}

// InlineCtor is a positional constructor call used as a value, e.g.
// `Foo(1.0, bar)` inside `Bar bar(foo = Foo(1.0, bar))`
type InlineCtor struct {
	Type string   `parser:"@Ident"`
	Args []*Value `parser:"\"(\" (@@ (\",\" @@)*)? \")\""`
}

type MissionStanza struct {
	Start  string         `parser:"\"Mission\" \":\" \"Start\" @Ident"`
	Blocks []*DuringBlock `parser:"@@*"`
}

type DuringBlock struct {
	Action string  `parser:"\"During\" @Ident \":\""`
	Rules  []*Rule `parser:"@@*"`
}

type Rule struct {
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
	{Name: "Path", Pattern: `[a-zA-Z][a-zA-Z_\d]*(?:[./][a-zA-Z_\d-]+)+`},
	{Name: "Arrow", Pattern: `->`},
	{Name: "Float", Pattern: `-?\d+(?:\.\d+)?`},
	{Name: "Int", Pattern: `-?\d+`},
	{Name: "String", Pattern: `'[^']*'|"[^"]*"`},
	{Name: "Ident", Pattern: `[a-zA-Z][a-zA-Z_\d]`},
	{Name: "Punct", Pattern: `[:(),=\[\]]`},
	{Name: "Whitespace", Pattern: `[ \t\r\n]+`},
})

var dslParser = participle.MustBuild[File](
	participle.Lexer(dslLexer),
	participle.Elide("Whitespace", "Comment"),
	participle.UseLookahead(2),
)

func Parse(filename string, r io.Reader) (*File, error) {
	return dslParser.Parse(filename, r)
}
