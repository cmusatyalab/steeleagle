package vehicle

import (
	"fmt"
	"testing"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
)

// TestDmsHolds checks that the vehicle holds once a velocity target is not
// followed by another control call, and only once.
func TestDmsHolds(t *testing.T) {
	v, driver := newTestVehicle(t)
	client := driverpb.NewControlServiceClient(v.conn)
	if _, err := client.SetVelocityTarget(callCtx(t), &driverpb.SetVelocityTargetRequest{}); err != nil {
		t.Fatal(err)
	}
	if n := driver.holdCount(); n != 0 {
		t.Fatalf("held %d times right after the velocity target, want 0", n)
	}
	time.Sleep(3 * DmsTimeout)
	if n := driver.holdCount(); n != 1 {
		t.Errorf("held %d times, want 1", n)
	}
}

// TestDmsVelocityTargetsRearm checks that a stream of velocity targets
// doesn't hold until it stops.
func TestDmsVelocityTargetsRearm(t *testing.T) {
	// The targets come far more often than the timeout, so a slow machine
	// doesn't let it pass between them
	timeout := DmsTimeout
	DmsTimeout = time.Second
	t.Cleanup(func() { DmsTimeout = timeout })
	v, driver := newTestVehicle(t)
	client := driverpb.NewControlServiceClient(v.conn)
	for range 5 {
		if _, err := client.SetVelocityTarget(callCtx(t), &driverpb.SetVelocityTargetRequest{}); err != nil {
			t.Fatal(err)
		}
		time.Sleep(DmsTimeout / 10)
	}
	if n := driver.holdCount(); n != 0 {
		t.Fatalf("held %d times during velocity targets, want 0", n)
	}
	eventually(t, 5*time.Second, func() error {
		if n := driver.holdCount(); n != 1 {
			return fmt.Errorf("held %d times, want 1", n)
		}
		return nil
	})
}

// TestDmsDisarmedByControl checks that another control call disarms the
// switch, and that gimbal velocity targets don't arm it.
func TestDmsDisarmedByControl(t *testing.T) {
	v, driver := newTestVehicle(t)
	client := driverpb.NewControlServiceClient(v.conn)
	if _, err := client.SetVelocityTarget(callCtx(t), &driverpb.SetVelocityTargetRequest{}); err != nil {
		t.Fatal(err)
	}
	if _, err := client.SetGimbalVelocityTarget(callCtx(t), &driverpb.SetGimbalVelocityTargetRequest{}); err != nil {
		t.Fatal(err)
	}
	time.Sleep(3 * DmsTimeout)
	if n := driver.holdCount(); n != 0 {
		t.Errorf("held %d times, want 0", n)
	}
}
