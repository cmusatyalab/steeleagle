package vehicle

import (
	"testing"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/rs/zerolog"
)

// TestUpdateFailsafe checks the failsafe state follows the lost planes, and
// that only a newly lost plane has its behavior carried out.
func TestUpdateFailsafe(t *testing.T) {
	v := &Vehicle{
		failsafe:        vehiclepb.FailsafeState_FAILSAFE_STATE_NONE,
		controlBehavior: vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_HOLD,
		dataBehavior:    vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_RTH,
		log:             zerolog.Nop(),
	}
	steps := []struct {
		control, data bool
		state         vehiclepb.FailsafeState
		behavior      vehiclepb.FailsafeBehavior
		run           bool
	}{
		{false, false, vehiclepb.FailsafeState_FAILSAFE_STATE_NONE, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE, false},
		{false, true, vehiclepb.FailsafeState_FAILSAFE_STATE_NO_DATA, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_RTH, true},
		{false, true, vehiclepb.FailsafeState_FAILSAFE_STATE_NO_DATA, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE, false},
		{true, true, vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL_NO_DATA, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_HOLD, true},
		{true, false, vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE, false},
		{false, false, vehiclepb.FailsafeState_FAILSAFE_STATE_NONE, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE, false},
		// Both lost at once: control takes precedence
		{true, true, vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL_NO_DATA, vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_HOLD, true},
	}
	for i, s := range steps {
		behavior, run := v.updateFailsafe(s.control, s.data)
		if v.failsafe != s.state || behavior != s.behavior || run != s.run {
			t.Errorf("step %d: state = %v, behavior = %v, run = %v; want %v, %v, %v",
				i, v.failsafe, behavior, run, s.state, s.behavior, s.run)
		}
	}

	// Data behavior runs when control is lost at the same time but has none
	v.failsafe = vehiclepb.FailsafeState_FAILSAFE_STATE_NONE
	v.controlBehavior = vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE
	if behavior, run := v.updateFailsafe(true, true); behavior != vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_RTH || !run {
		t.Errorf("behavior = %v, run = %v; want RTH, true", behavior, run)
	}
}
