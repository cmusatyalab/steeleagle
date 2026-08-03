package main

var wantedPackages = []string{
	"steeleagle_protocol.v1.services.driver.control",
	"steeleagle_protocol.v1.messages.telemetry",
	"steeleagle_protocol.v1.messages.result",
	"steeleagle_protocol.v1",
}

var hiddenMessages = []string{
	"steeleagle_protocol.v1.messages.telemetry.RawFrame",
	"steeleagle_protocol.v1.messages.telemetry.EncodedFrame",
}
