package compiler

// overlayDir is the directory, relative to the workspace, that Compile
// writes overlay files into for go build. The leading dot keeps the go tool
// from treating it as a package.
const overlayDir = ".overlay"

// modulesDir is the directory, relative to the workspace, that modules
// downloaded for a mission are copied into, out of the module cache. The
// leading dot keeps the go tool from treating it as a package.
const modulesDir = ".modules"

// sdkModPath is the path of the SDK's module, which every mission builds
// against.
const sdkModPath = "github.com/cmusatyalab/steeleagle/sdk"

// outputDefault is the default output file for a mission compile, a DSL
// binary.
const outputDefault = "mission.dslb"
