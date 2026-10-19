module github.com/cmusatyalab/steeleagle/api/go

go 1.26.5

// Go reads retractions from the latest release's go.mod, so keep this in
// every future version.

retract [v0.1.0, v0.3.0] // Pre-v4 protocol; use v0.4.0 or later.

require (
	google.golang.org/grpc v1.83.0
	google.golang.org/protobuf v1.36.11
)

require (
	golang.org/x/net v0.55.0 // indirect
	golang.org/x/sys v0.45.0 // indirect
	golang.org/x/text v0.37.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20260526163538-3dc84a4a5aaa // indirect
)
