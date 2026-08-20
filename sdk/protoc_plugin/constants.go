package main

import "google.golang.org/protobuf/compiler/protogen"

// sdkImportPath is the Go import path for core_iface.pb.go and core_msg.pb.go.
const sdkImportPath protogen.GoImportPath = "github.com/cmusatyalab/steeleagle/sdk"

// enumsImportPath is the Go import path for core_enums.pb.go.
const enumsImportPath protogen.GoImportPath = "github.com/cmusatyalab/steeleagle/sdk/enums"

// commonPackage is the package that holds SteelEagle protocol common types.
const commonPackage = "steeleagle_protocol.v1.common"

// fieldNotPresentError is the name of the error returned when a field is not set.
const fieldNotPresentError = "ErrFieldNotPresent"

// excludeTagPrefix/privateTagPrefix are the #exclude-requires and
// #private-requires directive comments that signal the compiler to
// selectively ignore interfaces/enums if they are unsupported.
const (
	excludeTagPrefix = "// #exclude-ifndef "
	privateTagPrefix = "// #private-ifndef "
)

// wantedPackages are the subset of the SteelEagle API available to SteelEagle
// SDK user code.
var wantedPackages = []string{
	"steeleagle_protocol.v1.services.driver",
	"steeleagle_protocol.v1.messages.telemetry",
	"steeleagle_protocol.v1.messages.result",
	"steeleagle_protocol.v1.common",
}

// hiddenMessages are messages within the wantedPackages that we don't want to
// generate user bindings for.
var hiddenMessages = []string{
	"steeleagle_protocol.v1.services.driver.*Request",
	"steeleagle_protocol.v1.services.driver.Calibrate*",
	"steeleagle_protocol.v1.services.driver.Stream*",
	"steeleagle_protocol.v1.services.driver.GetVideo*",
	"steeleagle_protocol.v1.messages.telemetry.RawFrame",
	"steeleagle_protocol.v1.messages.telemetry.EncodedFrame",
}
