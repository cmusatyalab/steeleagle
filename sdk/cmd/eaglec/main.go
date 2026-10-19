// Command eaglec builds SteelEagle programs with the SDK preprocessed
// for a vehicle. It has four modes:
//
//	eaglec sdk [-cap file] [-manifest file] [-geojson file] [-o file] [packages]
//	eaglec dsl [-json] [-cap file] [-manifest file] [-geojson file] [-o file] mission
//	eaglec schema [-json] [-cap file] [-manifest file] [-geojson file] mission
//	eaglec parse mission.dsl
//
// An SDK compile runs go build on packages (the package in the working
// directory by default) in the local Go module, with the module's and the
// SDK's packages scrubbed according to the cap file and with the consts
// named by the manifest and GeoJSON generated into them.
//
// A DSL compile compiles a mission in a temporary workspace, preprocessing
// the SDK the same way, into a DSL binary (mission.dslb by default).
//
// A schema run loads the types available to a mission, preprocessed the
// same way, and prints the type registry as JSON. Only the mission's
// Modules: and Imports: stanzas are used, so the rest may be left out.
//
// A parse run parses a DSL mission file and prints it as JSON, in the form
// the -json flag of the dsl and schema modes reads (see
// parser.ParseFromJson).
//
// The dsl and schema modes read the mission as DSL, or as JSON with -json.
// Relative module override paths in a JSON mission are resolved against
// the working directory, and in a DSL file against the file's directory.
// Every mode takes -errors=json to print each error as a JSON object on
// its own line ({"file", "decl", "line", "message"}) instead of as text.
//
// The sdk and dsl modes take GOOS, GOARCH and the rest of the go tool's
// environment from the process's, except that cgo is disabled so binaries
// are static.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
)

const usage = `usage:
  eaglec sdk [flags] [packages]     build Go packages in the local module
  eaglec dsl [flags] mission        compile a DSL mission
  eaglec schema [flags] mission     print the types available to a mission as JSON
  eaglec parse [flags] mission.dsl  print a DSL mission as JSON

Run "eaglec <mode> -h" for the flags of a mode.
`

// errorFormat is how main prints errors: "text" or "json". Every mode
// sets it with its -errors flag.
var errorFormat = "text"

func main() {
	if len(os.Args) < 2 {
		fmt.Fprint(os.Stderr, usage)
		os.Exit(2)
	}
	var errs []*buildtools.CompileError
	switch mode, args := os.Args[1], os.Args[2:]; mode {
	case "sdk":
		errs = compileSdk(args)
	case "dsl":
		errs = compileDsl(args)
	case "schema":
		errs = printSchema(args, os.Stdout)
	case "parse":
		errs = printParse(args, os.Stdout)
	case "-h", "-help", "--help", "help":
		fmt.Print(usage)
		return
	default:
		fmt.Fprintf(os.Stderr, "unknown mode %q\n%s", mode, usage)
		os.Exit(2)
	}
	if len(errs) > 0 {
		for _, e := range errs {
			fmt.Fprintln(os.Stderr, formatError(e, errorFormat))
		}
		os.Exit(1)
	}
}

// compileSdk runs an SDK compile with the command line arguments args.
func compileSdk(args []string) []*buildtools.CompileError {
	fs, files := newFlagSet("sdk", "[packages]")
	out := fs.String("o", "", "output file (optional; defaults to go build's)")
	parseFlags(fs, args)
	options, err := files.options()
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	return buildtools.BuildSdk(".", fs.Args(), append(options, buildtools.WithOutputFile(*out))...)
}

// compileDsl runs a DSL compile with the command line arguments args.
func compileDsl(args []string) []*buildtools.CompileError {
	fs, files := newFlagSet("dsl", "mission")
	out := fs.String("o", "mission.dslb", "output file")
	asJson := fs.Bool("json", false, "read the mission as JSON instead of DSL")
	parseFlags(fs, args)
	if fs.NArg() != 1 {
		fs.Usage()
		os.Exit(2)
	}
	options, err := files.options()
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	src, err := source(fs.Arg(0), *asJson)
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	return compiler.Compile(src, append(options, buildtools.WithOutputFile(*out))...)
}

// printSchema runs a schema run with the command line arguments args,
// writing the type registry to stdout.
func printSchema(args []string, stdout io.Writer) []*buildtools.CompileError {
	fs, files := newFlagSet("schema", "mission")
	asJson := fs.Bool("json", false, "read the mission as JSON instead of DSL")
	parseFlags(fs, args)
	if fs.NArg() != 1 {
		fs.Usage()
		os.Exit(2)
	}
	options, err := files.options()
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	src, err := source(fs.Arg(0), *asJson)
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	registry, errs := compiler.Load(src, options...)
	if len(errs) > 0 {
		return errs
	}
	if _, err := stdout.Write(append(registry, '\n')); err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	return nil
}

// printParse runs a parse run with the command line arguments args,
// writing the mission as JSON to stdout.
func printParse(args []string, stdout io.Writer) []*buildtools.CompileError {
	fs := newBaseFlagSet("parse", "mission.dsl")
	parseFlags(fs, args)
	if fs.NArg() != 1 {
		fs.Usage()
		os.Exit(2)
	}
	ast, err := parser.ParseFromFile(fs.Arg(0))
	if err != nil {
		return []*buildtools.CompileError{{Err: err, File: fs.Arg(0)}}
	}
	out, err := astJson(ast)
	if err != nil {
		return []*buildtools.CompileError{{Err: err, File: fs.Arg(0)}}
	}
	if _, err := stdout.Write(append(out, '\n')); err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	return nil
}

// source returns the mission at path, read as JSON if asJson and as DSL
// otherwise.
func source(path string, asJson bool) (compiler.Source, error) {
	if !asJson {
		return compiler.FromFile(path), nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return compiler.FromJson(data), nil
}

// astJson encodes ast as JSON in the form parser.ParseFromJson reads: the
// Ast's fields under their Go names, without positions or absent values,
// and with String values unquoted (ParseFromJson quotes them again).
func astJson(ast *parser.Ast) ([]byte, error) {
	raw, err := json.Marshal(ast)
	if err != nil {
		return nil, err
	}
	// UseNumber keeps Int values exact, which float64 can't past 2^53
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var tree any
	if err := dec.Decode(&tree); err != nil {
		return nil, err
	}
	return json.Marshal(cleanAst(tree))
}

// cleanAst drops every Pos key and null value from a decoded Ast, and
// strips the quotes from the raw String tokens the parser captured.
func cleanAst(v any) any {
	switch v := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(v))
		for k, e := range v {
			if k == "Pos" || e == nil {
				continue
			}
			if s, ok := e.(string); ok && k == "String" && len(s) >= 2 {
				e = s[1 : len(s)-1]
			}
			out[k] = cleanAst(e)
		}
		return out
	case []any:
		for i, e := range v {
			v[i] = cleanAst(e)
		}
		return v
	}
	return v
}

// inputFiles are the paths of the optional input files the sdk, dsl and
// schema modes take.
type inputFiles struct {
	cap, manifest, geoJson string
}

// newBaseFlagSet returns a flag set for mode with the -errors flag every
// mode takes. args describes the mode's positional arguments in its usage.
func newBaseFlagSet(mode, args string) *flag.FlagSet {
	fs := flag.NewFlagSet(mode, flag.ExitOnError)
	fs.Usage = func() {
		fmt.Fprintf(fs.Output(), "usage: eaglec %s [flags] %s\n", mode, args)
		fs.PrintDefaults()
	}
	fs.StringVar(&errorFormat, "errors", "text", `error output format, "text" or "json"`)
	return fs
}

// newFlagSet returns a base flag set for mode, with the input file flags
// bound to the returned inputFiles.
func newFlagSet(mode, args string) (*flag.FlagSet, *inputFiles) {
	fs := newBaseFlagSet(mode, args)
	files := &inputFiles{}
	fs.StringVar(&files.cap, "cap", "", "vehicle cap file (optional; nothing is scrubbed without one)")
	fs.StringVar(&files.manifest, "manifest", "", "mission manifest file (optional)")
	fs.StringVar(&files.geoJson, "geojson", "", "mission GeoJSON file (optional)")
	return fs, files
}

// parseFlags parses args into fs, exiting with fs's usage if -errors names
// an unknown format.
func parseFlags(fs *flag.FlagSet, args []string) {
	fs.Parse(args)
	if errorFormat != "text" && errorFormat != "json" {
		fmt.Fprintf(fs.Output(), "unknown -errors format %q\n", errorFormat)
		fs.Usage()
		os.Exit(2)
	}
}

// options reads the input files that were given, and returns the build
// options that pass them on.
func (f *inputFiles) options() ([]buildtools.Option, error) {
	var options []buildtools.Option
	for _, in := range []struct {
		path   string
		option func([]byte) buildtools.Option
	}{
		{f.cap, buildtools.WithCap},
		{f.manifest, buildtools.WithManifest},
		{f.geoJson, buildtools.WithGeoJson},
	} {
		if in.path == "" {
			continue
		}
		data, err := os.ReadFile(in.path)
		if err != nil {
			return nil, err
		}
		options = append(options, in.option(data))
	}
	return options, nil
}

// jsonError is a compile error as -errors=json prints it.
type jsonError struct {
	File    string `json:"file"`
	Decl    string `json:"decl"`
	Line    uint32 `json:"line"`
	Message string `json:"message"`
}

// formatError formats a compile error in format: for "json", one JSON
// object; otherwise "file:line: error", leaving out whatever location it
// doesn't have.
func formatError(e *buildtools.CompileError, format string) string {
	if format == "json" {
		out, err := json.Marshal(jsonError{File: e.File, Decl: e.Decl, Line: e.LineNo, Message: e.Err.Error()})
		if err != nil {
			return e.Err.Error()
		}
		return string(out)
	}
	switch {
	case e.File != "" && e.LineNo > 0:
		return fmt.Sprintf("%s:%d: %v", e.File, e.LineNo, e.Err)
	case e.File != "":
		return fmt.Sprintf("%s: %v", e.File, e.Err)
	default:
		return e.Err.Error()
	}
}
