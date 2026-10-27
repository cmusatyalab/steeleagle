package vehicle

import (
	"testing"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
)

// TestGetFailsafeState checks that the failsafe state is reported with how
// long it has held.
func TestGetFailsafeState(t *testing.T) {
	v, _ := newTestVehicle(t)
	client := vehiclepb.NewSafetyServiceClient(v.conn)
	first, err := client.GetFailsafeState(callCtx(t), &vehiclepb.GetFailsafeStateRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if first.GetState() != vehiclepb.FailsafeState_FAILSAFE_STATE_NONE {
		t.Errorf("state = %v, want none", first.GetState())
	}
	second, err := client.GetFailsafeState(callCtx(t), &vehiclepb.GetFailsafeStateRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if second.GetTime().AsDuration() <= first.GetTime().AsDuration() {
		t.Errorf("time went from %v to %v, want it to grow", first.GetTime().AsDuration(),
			second.GetTime().AsDuration())
	}
}

// TestSetFailsafeBehavior checks that both failsafe behaviors are set, and
// that an unspecified behavior is hold.
func TestSetFailsafeBehavior(t *testing.T) {
	v, _ := newTestVehicle(t)
	client := vehiclepb.NewSafetyServiceClient(v.conn)
	for _, tc := range []struct {
		set, want vehiclepb.FailsafeBehavior
	}{
		{vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_RTH, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_RTH},
		{vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_MISSION, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_MISSION},
		{vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_UNSPECIFIED, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_HOLD},
	} {
		_, err := client.SetControlFailsafeBehavior(callCtx(t),
			vehiclepb.SetControlFailsafeBehaviorRequest_builder{Behavior: tc.set}.Build())
		if err != nil {
			t.Fatal(err)
		}
		_, err = client.SetDataFailsafeBehavior(callCtx(t),
			vehiclepb.SetDataFailsafeBehaviorRequest_builder{Behavior: tc.set}.Build())
		if err != nil {
			t.Fatal(err)
		}
		v.safetyMu.Lock()
		control, data := v.controlBehavior, v.dataBehavior
		v.safetyMu.Unlock()
		if control != tc.want || data != tc.want {
			t.Errorf("set %v: control = %v, data = %v, want %v", tc.set, control, data, tc.want)
		}
	}
}
