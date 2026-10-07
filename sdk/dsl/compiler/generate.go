package compiler

import (
	_ "embed"
	"fmt"
	"go/format"
	"os"
	"path/filepath"
	"strings"
	"text/template"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/linker"
)

//go:embed main.go.tmpl
var mainTemplateSource string
var mainTemplate = template.Must(template.New("main.go.tmpl").Parse(mainTemplateSource))

// templateData is the top-level value main.go.tmpl is executed with.
type templateData struct {
	*linker.IR
	CapTOML      string
	ManifestTOML string
	GeoJSON      string
}

// Generate renders a linked IR as a runnable main.go inside a given
// workspace directory, embedding the cap, manifest, and GeoJSON files
// verbatim so the built binary can reconstruct them without the
// original files.
func Generate(ir *linker.IR, capTOML, manifestTOML, geoJSON []byte, workspace string) *sdk.CompileError {
	data := &templateData{
		IR:           ir,
		CapTOML:      string(capTOML),
		ManifestTOML: string(manifestTOML),
		GeoJSON:      string(geoJSON),
	}

	var buf strings.Builder
	if err := mainTemplate.Execute(&buf, data); err != nil {
		return &sdk.CompileError{Err: fmt.Errorf("executing main.go template: %w", err), File: "main.go"}
	}

	formatted, err := format.Source([]byte(buf.String()))
	if err != nil {
		return &sdk.CompileError{
			Err:  fmt.Errorf("generated main.go is not valid Go: %w\n%s", err, buf.String()),
			File: "main.go",
		}
	}
	if err := os.WriteFile(filepath.Join(workspace, "main.go"), formatted, 0o644); err != nil {
		return &sdk.CompileError{Err: err, File: "main.go"}
	}
	return nil
}
