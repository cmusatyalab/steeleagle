package vehicle_test

import (
    "testing"
)

func TestProxy(t *testing.T) {
    // TODO: test socket proxying between driver and mission, and
    // ensure that the stream service is not visible
}

func TestPolicy(t *testing.T) {
    // TODO: test permissions + state transitions with the basic law
    // and then with a custom law
}

func TestTelemetry(t *testing.T) {
    // TODO: test getting telemetry stream
}

func TestVideoFrames(t *testing.T) {
    // TODO: test getting video frame stream
}

func TestRTSPStream(t *testing.T) {
    // TODO: test redirecting RTSP stream/re-encoding
}

func TestPluginConfig(t *testing.T) {
    // TODO: start vehicle without a driver and then without a mission,
    // see how error states are handled
}

func TestDMSFailsafe(t *testing.T) {
    // TODO: dead man's switch failsafe
}

func TestServerFailsafe(t *testing.T) {
    // TODO: server dc failsafe
}

func TestMissionFailsafe(t *testing.T) {
    // TODO: server dc failsafe
}

func TestAbandonFailsafe(t *testing.T) {
    // TODO: server and mission dc failsafe
}
