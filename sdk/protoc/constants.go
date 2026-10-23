package main

import "google.golang.org/protobuf/compiler/protogen"

// sdkImportPath is the Go import path for core_iface.pb.go and core_msg.pb.go.
const sdkImportPath protogen.GoImportPath = "github.com/cmusatyalab/steeleagle/sdk"

// enumsImportPath is the Go import path for core_enums.pb.go.
const enumsImportPath protogen.GoImportPath = "github.com/cmusatyalab/steeleagle/sdk/enums"

// commonPackage is the package that holds SteelEagle protocol common types.
const commonPackage = "steeleagle_protocol.v1.common"

// capPathRoot is the root that every capability path emitted in a
// preprocessor directive is qualified with.
const capPathRoot = "steeleagle_protocol/v1/"

// undirectedPathRoots are capability path roots that never get a
// preprocessor directive: result messages come from compute engines, not
// the vehicle, so a cap file never masks them.
var undirectedPathRoots = []string{
	capPathRoot + "messages/result/",
}

// fieldNotPresentError is the name of the error returned when a field is not set.
const fieldNotPresentError = "ErrFieldNotPresent"

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
}
