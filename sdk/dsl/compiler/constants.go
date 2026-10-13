package compiler

// overlayDir is the directory, relative to the workspace, that Compile
// writes overlay files into for go build. The leading dot keeps the go tool
// from treating it as a package.
const overlayDir = ".overlay"

// outputDefault is the default output file for a mission compile, a DSL
// binary.
const outputDefault = "mission.dslb"
