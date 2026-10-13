package compiler

import (
	"fmt"
	"path/filepath"

	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
)

// Source is a mission to compile or load, created by FromFile, FromSource
// or FromJson.
type Source interface {
	// parse parses the mission, returning the directory relative module
	// override paths are resolved against.
	parse() (ast *parser.Ast, dir string, err error)
}

// fileSource is a DSL mission file path.
type fileSource string

// dslSource is DSL mission source text.
type dslSource []byte

// jsonSource is a JSON-encoded mission.
type jsonSource []byte

// FromFile reads a mission from the DSL file at path. Relative module
// override paths are resolved against the file's directory.
func FromFile(path string) Source {
	return fileSource(path)
}

// FromSource reads a mission from DSL source text. Relative module
// override paths are resolved against the working directory.
func FromSource(src []byte) Source {
	return dslSource(src)
}

// FromJson reads a mission from its JSON encoding (see
// parser.ParseFromJson). Relative module override paths are resolved
// against the working directory.
func FromJson(data []byte) Source {
	return jsonSource(data)
}

func (s fileSource) parse() (*parser.Ast, string, error) {
	ast, err := parser.ParseFromFile(string(s))
	return ast, filepath.Dir(string(s)), err
}

func (s dslSource) parse() (*parser.Ast, string, error) {
	ast, err := parser.ParseFromSource(s)
	return ast, ".", err
}

func (s jsonSource) parse() (*parser.Ast, string, error) {
	ast, err := parser.ParseFromJson(s)
	return ast, ".", err
}

// parseMission parses a mission from src, then makes every relative module
// override path absolute, since the go tool runs in a temporary workspace
// that relative paths would otherwise be resolved against.
func parseMission(src Source) (*parser.Ast, error) {
	if src == nil {
		return nil, fmt.Errorf("no mission given")
	}
	ast, dir, err := src.parse()
	if err != nil {
		return nil, err
	}
	if err := absOverrides(ast, dir); err != nil {
		return nil, err
	}
	return ast, nil
}

// absOverrides makes every relative module override path in ast absolute
// by resolving it against dir.
func absOverrides(ast *parser.Ast, dir string) error {
	for _, mod := range ast.Modules.Modules {
		if mod.Override == "" || filepath.IsAbs(mod.Override) {
			continue
		}
		abs, err := filepath.Abs(filepath.Join(dir, mod.Override))
		if err != nil {
			return fmt.Errorf("resolving override path %s for module %s: %w", mod.Override, mod.Path, err)
		}
		mod.Override = abs
	}
	return nil
}
