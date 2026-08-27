package main

import (
	_ "embed"
	"fmt"
	"go/format"
	"os"
	"path/filepath"
	"strings"
	"text/template"
)

//go:embed main.go.tmpl
var mainTemplateSource string

var mainTemplate = template.Must(template.New("main.go.tmpl").Parse(mainTemplateSource))

// templateData is the top-level value main.go.tmpl is executed with.
type templateData struct {
	*irResult
	CapTOML string
	GeoJSON string
}

// Generate renders ir as a complete main.go (embedding capTOML and geoJSON
// verbatim so the built binary can reconstruct its CapFile/Map without the
// original files) and writes it to filepath.Join(dir, "main.go").
func Generate(ir *irResult, capTOML, geoJSON []byte, dir string) error {
	data := &templateData{irResult: ir, CapTOML: string(capTOML), GeoJSON: string(geoJSON)}

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
