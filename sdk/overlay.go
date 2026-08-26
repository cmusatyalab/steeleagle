package sdk

import (
	_ "embed"
	"errors"
	"os"

	"github.com/cmusatyalab/steeleagle/sdk/preprocess"
	"golang.org/x/tools/go/packages"
)

// Target source packages for const generation.
const (
	sdkParamsPkgPath = "github.com/cmusatyalab/steeleagle/sdk/params"
	dslInfoPkgPath   = "github.com/cmusatyalab/steeleagle/sdk/dsl/info"
)

//go:embed params/params.go
var sdkParamsSource []byte

//go:embed dsl/info/info.go
var dslInfoSource []byte

// CreateOverlay creates a Go compiler overlay that replaces source files
// with files scrubbed according to pre-processor directives, and rewrites
// sdk/params/params.go and dsl/info/info.go to declare the params/info
// constants named by sdkParams and dslInfo respectively (see
// preprocess.GenerateConsts).
func CreateOverlay(capFile *CapFile, sdkTypes, dslTypes map[string][]string, pkgs []*packages.Package) (map[string][]byte, []*CompileError) {
	overlay := map[string][]byte{}
	var compileErrors []*CompileError
	for _, pkg := range pkgs {
		// Check if this package is a package that contains consts to generate
		constSrc, consts, isConstPkg := constSourceFor(pkg.PkgPath, sdkTypes, dslTypes)
		for _, file := range pkg.GoFiles {
			if isConstPkg {
				gen, err := preprocess.GenerateConsts(consts, constSrc)
				if err != nil {
					compileErrors = append(compileErrors, toCompileError(err, pkg.PkgPath))
					continue
				}
				overlay[file] = gen
				continue
			}

			src, err := os.ReadFile(file)
			if err != nil {
				compileErrors = append(compileErrors, toCompileError(err, pkg.PkgPath))
				continue
			}
			scrubbed, dirty, err := preprocess.Scrub(capFile.Supports, src)
			if err != nil {
				compileErrors = append(compileErrors, toCompileError(err, pkg.PkgPath))
				continue
			}
			if dirty { // only overwrite file if it was changed
				overlay[file] = scrubbed
			}
		}
	}
	return overlay, compileErrors
}

// toCompileError wraps a plain error err, or a *preprocess.PreprocessError
// into a CompileError attributed to file. If err is (or wraps) a
// *preprocess.PreprocessError, its LineNo carries over, otherwise LineNo is
// left zero.
func toCompileError(err error, file string) *CompileError {
	compileErr := &CompileError{error: err, File: file}
	var preprocessErr *preprocess.PreprocessError
	if errors.As(err, &preprocessErr) {
		compileErr.LineNo = preprocessErr.LineNo
	}
	return compileErr
}

// constSourceFor returns the embedded go file source for pkgPath, and
// the type map that belongs to it.
func constSourceFor(pkgPath string, sdkTypes, dslTypes map[string][]string) ([]byte, map[string][]string, bool) {
	switch pkgPath {
	case sdkParamsPkgPath:
		return sdkParamsSource, sdkTypes, true
	case dslInfoPkgPath:
		return dslInfoSource, dslTypes, true
	default:
		return nil, nil, false
	}
}
