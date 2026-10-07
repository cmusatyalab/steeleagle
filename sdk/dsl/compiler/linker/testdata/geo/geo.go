// Package geo holds a fixture Datatype in a package whose name collides
// with one of the packages main.go.tmpl always imports
// (github.com/cmusatyalab/steeleagle/sdk/geo), so linker_test.go can check
// that using it unaliased is reported instead of generating code that
// doesn't compile.
package geo

import "github.com/cmusatyalab/steeleagle/sdk/dsl"

// Spot is a fixture Datatype.
type Spot struct {
	X float64
}

func (*Spot) Type() {}

var _ dsl.Datatype = &Spot{}
