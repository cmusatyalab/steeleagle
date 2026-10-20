package compiler

import (
	_ "embed"
	"fmt"
	"go/format"
	"os"
	"path/filepath"
	"strings"
	"text/template"

	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/linker"
)

//go:embed main.go.tmpl
var mainTemplateSource string
var mainTemplate = template.Must(template.New("main.go.tmpl").Parse(mainTemplateSource))

// templateData is the top-level value main.go.tmpl is executed with.
type templateData struct {
	*linker.IR
	PluginToml   string
	ManifestToml string
	GeoJson      string
}

// generate renders a linked IR as a runnable main.go inside the workspace
// directory dir, embedding the cap, manifest, and GeoJSON files of cfg
// verbatim so the built binary can reconstruct them without the original
// files.
func generate(ir *linker.IR, cfg *buildtools.Config, dir string) error {
	data := &templateData{
		IR:           ir,
		PluginToml:   string(cfg.PluginToml),
		ManifestToml: string(cfg.ManifestToml),
		GeoJson:      string(cfg.GeoJson),
	}

	var buf strings.Builder
	if err := mainTemplate.Execute(&buf, data); err != nil {
		return fmt.Errorf("executing main.go template: %w", err)
	}

	formatted, err := format.Source([]byte(buf.String()))
	if err != nil {
		return fmt.Errorf("generated main.go is not valid Go: %w\n%s", err, buf.String())
	}
	return os.WriteFile(filepath.Join(dir, "main.go"), formatted, 0o644)
}
