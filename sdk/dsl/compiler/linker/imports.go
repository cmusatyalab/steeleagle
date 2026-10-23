package linker

import (
	"maps"
	"slices"
)

// fixedImports are the packages main.go.tmpl always imports, keyed by
// import path, with the identifier each is referenced by. This must be
// kept in sync with main.go.tmpl.
var fixedImports = map[string]string{
	"context":                "context",
	"net":                    "net",
	"os":                     "os",
	"os/signal":              "signal",
	"syscall":                "syscall",
	"github.com/rs/zerolog":  "zerolog",
	"google.golang.org/grpc": "grpc",
	"google.golang.org/grpc/credentials/insecure":   "insecure",
	"github.com/cmusatyalab/steeleagle/sdk":         "sdk",
	"github.com/cmusatyalab/steeleagle/sdk/dsl":     "dsl",
	"github.com/cmusatyalab/steeleagle/sdk/dsl/fsm": "fsm",
	"github.com/cmusatyalab/steeleagle/sdk/geo":     "geo",
	"github.com/cmusatyalab/steeleagle/sdk/params":  "params",
}

// FixedImportPaths returns the import paths main.go.tmpl always imports,
// sorted.
func FixedImportPaths() []string {
	return slices.Sorted(maps.Keys(fixedImports))
}
