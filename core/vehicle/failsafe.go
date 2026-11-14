package vehicle

import (
	"context"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
)

// monitorFailsafe starts a goroutine for the run of ctx that polls the
// vehicle's control and data planes every FailsafePollInterval. Control is
// lost when the daemon loses contact with its orchestrator, and data when the
// Uriel client loses contact with the RCS. When a plane is lost, the vehicle
// enters the matching failsafe state and carries out that plane's failsafe
// behavior; when it comes back, the state is updated, but nothing is done.
func (v *Vehicle) monitorFailsafe(ctx context.Context) {
	// The connections are taken now, while the run holds them
	daemon := daemonpb.NewDaemonServiceClient(v.daemonConn)
	driver := v.driverInfo.conn
	client := v.uriel
	hasRemote := v.compute.rcs != ""
	// Each run starts out of failsafe, so a plane still lost from the last
	// run has its behavior carried out again
	v.safetyMu.Lock()
	v.failsafe = vehiclepb.FailsafeState_FAILSAFE_STATE_NONE
	v.failsafeTime = time.Now()
	v.safetyMu.Unlock()

	go func() {
		ticker := time.NewTicker(FailsafePollInterval)
		defer ticker.Stop()
		var controlLost, dataLost bool
		// The remote connection is only made after the client starts, so data
		// is not lost until it has been connected once
		dataSeen := false
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
			}

			// A failed check leaves its plane as it was, so a slow or
			// failed call doesn't trigger a failsafe on its own
			pollCtx, cancel := context.WithTimeout(ctx, FailsafePollInterval)
			resp, err := daemon.GetConnectionStatus(
				pollCtx, &daemonpb.GetConnectionStatusRequest{}, grpc.WaitForReady(true),
			)
			cancel()
			if err == nil {
				controlLost = !resp.GetConnected()
			} else if ctx.Err() == nil {
				v.log.Debug().Err(err).Msg("could not check control connection")
			}
			if hasRemote {
				connected, err := client.IsRemoteConnected()
				if err == nil {
					dataSeen = dataSeen || connected
					dataLost = dataSeen && !connected
				} else if ctx.Err() == nil {
					v.log.Debug().Err(err).Msg("could not check data connection")
				}
			}
			if ctx.Err() != nil {
				return
			}

			behavior, changed := v.updateFailsafe(controlLost, dataLost)
			if changed {
				v.runFailsafeBehavior(ctx, driver, behavior)
			}
		}
	}()
}

// updateFailsafe sets the failsafe state from which planes are lost, and
// returns the behavior to carry out, and whether there is one. Only a newly
// lost plane has its behavior carried out; when both are lost at once, the
// control behavior takes precedence, unless it is none.
func (v *Vehicle) updateFailsafe(controlLost, dataLost bool) (vehiclepb.FailsafeBehavior, bool) {
	var state vehiclepb.FailsafeState
	switch {
	case controlLost && dataLost:
		state = vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL_NO_DATA
	case controlLost:
		state = vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL
	case dataLost:
		state = vehiclepb.FailsafeState_FAILSAFE_STATE_NO_DATA
	default:
		state = vehiclepb.FailsafeState_FAILSAFE_STATE_NONE
	}

	v.safetyMu.Lock()
	defer v.safetyMu.Unlock()
	prev := v.failsafe
	if state == prev {
		return vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE, false
	}
	v.failsafe = state
	v.failsafeTime = time.Now()
	v.log.Warn().Stringer("from", prev).Stringer("to", state).Msg("failsafe state changed")

	wasControlLost := prev == vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL ||
		prev == vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL_NO_DATA
	wasDataLost := prev == vehiclepb.FailsafeState_FAILSAFE_STATE_NO_DATA ||
		prev == vehiclepb.FailsafeState_FAILSAFE_STATE_NO_CONTROL_NO_DATA
	behavior := vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE
	if controlLost && !wasControlLost {
		behavior = v.controlBehavior
	}
	if dataLost && !wasDataLost && behavior == vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE {
		behavior = v.dataBehavior
	}
	return behavior, behavior != vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE
}

// runFailsafeBehavior carries out a failsafe behavior with the driver on
// conn. Holding or returning home stops a running mission first, so that it
// can't command the vehicle after the failsafe does.
func (v *Vehicle) runFailsafeBehavior(
	ctx context.Context,
	conn *grpc.ClientConn,
	behavior vehiclepb.FailsafeBehavior,
) {
	v.log.Warn().Stringer("behavior", behavior).Msg("carrying out failsafe behavior")
	if behavior == vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_MISSION {
		v.missionMu.Lock()
		running := v.mission != nil && v.mission.Running()
		v.missionMu.Unlock()
		if running {
			v.log.Info().Str("mission", v.missionName).Msg("mission already running")
			return
		}
		ctx, cancel := context.WithTimeout(ctx, MissionStartTimeout)
		defer cancel()
		if _, err := v.StartMission(ctx, &missionpb.StartMissionRequest{}); err != nil {
			v.log.Error().Err(err).Msg("could not start mission for failsafe")
		}
		return
	}

	v.missionMu.Lock()
	v.stopMission()
	v.missionMu.Unlock()
	ctx, cancel := context.WithTimeout(ctx, FailsafeCommandTimeout)
	defer cancel()
	control := driverpb.NewControlServiceClient(conn)
	var err error
	switch behavior {
	case vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_HOLD:
		_, err = control.Hold(ctx, &driverpb.HoldRequest{})
	case vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_RTH:
		_, err = control.ReturnToHome(ctx, &driverpb.ReturnToHomeRequest{})
	}
	if err != nil {
		v.log.Error().Err(err).Stringer("behavior", behavior).
			Msg("could not carry out failsafe behavior")
	}
}
