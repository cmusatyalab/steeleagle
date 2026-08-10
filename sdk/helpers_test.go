package sdk

import (
	"testing"

	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"
)

// f32 is a shortform for a float32 cast from pointer.
func f32(v float32) *float32 { return &v }

// f64 is a shortform for a float64 cast from pointer.
func f64(v float64) *float64 { return &v }

// modeP is a shortform for a Mode cast from pointer, for use with
// Telemetry_builder.
func modeP(m telemetrypb.Mode) *telemetrypb.Mode { return &m }

// motionStatusP is a shortform for a MotionStatus cast from pointer, for use
// with Telemetry_builder.
func motionStatusP(m telemetrypb.MotionStatus) *telemetrypb.MotionStatus { return &m }

// mustAny packs a proto.Message into an Any, the same way a setpoint gets
// stored on PositionInfo.Setpoint / GimbalInfo.GimbalSetpoint, failing the
// test immediately if packing fails.
func mustAny(t *testing.T, m proto.Message) *anypb.Any {
	t.Helper()
	a, err := anypb.New(m)
	if err != nil {
		t.Fatalf("anypb.New: %v", err)
	}
	return a
}

// mustAnyNoT is mustAny for use in plain telemetry-building helpers that
// don't have a *testing.T in scope. anypb.New only fails for malformed
// proto registrations, which can't happen for the well-formed messages
// these tests build, so a panic here would only ever fire on a real bug.
func mustAnyNoT(m proto.Message) *anypb.Any {
	a, err := anypb.New(m)
	if err != nil {
		panic(err)
	}
	return a
}
