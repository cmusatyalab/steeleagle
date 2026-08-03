package main

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
	"steeleagle_protocol.v1.services.driver.Calibrate*",
	"steeleagle_protocol.v1.services.driver.Stream*",
	"steeleagle_protocol.v1.services.driver.GetVideo*",
	"steeleagle_protocol.v1.messages.telemetry.RawFrame",
	"steeleagle_protocol.v1.messages.telemetry.EncodedFrame",
}
