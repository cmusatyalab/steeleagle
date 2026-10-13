// Command eaglec builds SteelEagle programs with the SDK preprocessed
// for a vehicle. It has two modes:
//
//	eaglec sdk [-cap file] [-manifest file] [-geojson file] [-o file] [packages]
//	eaglec dsl [-cap file] [-manifest file] [-geojson file] [-o file] mission.dsl
//
// An SDK compile runs go build on packages (the package in the working
// directory by default) in the local Go module, with the module's and the
// SDK's packages scrubbed according to the cap file and with the consts
// named by the manifest and GeoJSON generated into them.
//
// A DSL compile compiles the mission in a DSL file in a temporary
// workspace, preprocessing the SDK the same way, into a DSL binary
// (mission.dslb by default).
//
// Both modes take GOOS, GOARCH and the rest of the go tool's environment
// from the process's, except that cgo is disabled so binaries are static.
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
)

const usage = `usage:
  eaglec sdk [flags] [packages]   build Go packages in the local module
  eaglec dsl [flags] mission.dsl  compile a DSL mission

Run "eaglec <mode> -h" for the flags of a mode.
`

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
	case "-h", "-help", "--help", "help":
		fmt.Print(usage)
		return
	default:
		fmt.Fprintf(os.Stderr, "unknown mode %q\n%s", mode, usage)
		os.Exit(2)
	}
	if len(errs) > 0 {
		for _, e := range errs {
			fmt.Fprintln(os.Stderr, formatError(e))
		}
		os.Exit(1)
	}
}

// compileSdk runs an SDK compile with the command line arguments args.
func compileSdk(args []string) []*buildtools.CompileError {
	fs, files := newFlagSet("sdk", "[packages]")
	out := fs.String("o", "", "output file (optional; defaults to go build's)")
	fs.Parse(args)
	options, err := files.options()
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	return buildtools.BuildSdk(".", fs.Args(), append(options, buildtools.WithOutputFile(*out))...)
}

// compileDsl runs a DSL compile with the command line arguments args.
func compileDsl(args []string) []*buildtools.CompileError {
	fs, files := newFlagSet("dsl", "mission.dsl")
	out := fs.String("o", "mission.dslb", "output file")
	fs.Parse(args)
	if fs.NArg() != 1 {
		fs.Usage()
		os.Exit(2)
	}
	options, err := files.options()
	if err != nil {
		return []*buildtools.CompileError{{Err: err}}
	}
	return compiler.Compile(compiler.FromFile(fs.Arg(0)), append(options, buildtools.WithOutputFile(*out))...)
}

// inputFiles are the paths of the optional input files both modes take.
type inputFiles struct {
	cap, manifest, geoJson string
}

// newFlagSet returns a flag set for mode, with the input file flags both
// modes take bound to the returned inputFiles. args describes the mode's
// positional arguments in its usage.
func newFlagSet(mode, args string) (*flag.FlagSet, *inputFiles) {
	fs := flag.NewFlagSet(mode, flag.ExitOnError)
	fs.Usage = func() {
		fmt.Fprintf(fs.Output(), "usage: eaglec %s [flags] %s\n", mode, args)
		fs.PrintDefaults()
	}
	files := &inputFiles{}
	fs.StringVar(&files.cap, "cap", "", "vehicle cap file (optional; nothing is scrubbed without one)")
	fs.StringVar(&files.manifest, "manifest", "", "mission manifest file (optional)")
	fs.StringVar(&files.geoJson, "geojson", "", "mission GeoJSON file (optional)")
	return fs, files
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

// formatError formats a compile error as "file:line: error", leaving out
// whatever location it doesn't have.
func formatError(e *buildtools.CompileError) string {
	switch {
	case e.File != "" && e.LineNo > 0:
		return fmt.Sprintf("%s:%d: %v", e.File, e.LineNo, e.Err)
	case e.File != "":
		return fmt.Sprintf("%s: %v", e.File, e.Err)
	default:
		return e.Err.Error()
	}
}
