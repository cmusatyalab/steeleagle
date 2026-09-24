package main_test

import (
	"runtime"
	"testing"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// TestGetStatusReportsPlatformBeforeConfigure checks that os/arch are reported
// by a fresh, never-configured daemon: they describe the running binary, not
// the applied config, so callers can read them before the first Configure.
func TestGetStatusReportsPlatformBeforeConfigure(t *testing.T) {
	inst := startEagled(t, "")

	resp, err := inst.Client.GetStatus(t.Context(), eagledpb.GetStatusRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if resp.GetConfigured() {
		t.Fatal("a fresh daemon must not report configured")
	}
	if resp.GetOs() != runtime.GOOS {
		t.Errorf("os = %q, want %q", resp.GetOs(), runtime.GOOS)
	}
	if resp.GetArch() != runtime.GOARCH {
		t.Errorf("arch = %q, want %q", resp.GetArch(), runtime.GOARCH)
	}
}
