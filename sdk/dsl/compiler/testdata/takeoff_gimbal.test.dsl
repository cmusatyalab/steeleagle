Role Patrol:
Import:
    "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
    "github.com/cmusatyalab/steeleagle/sdk/dsl/types"
    "github.com/cmusatyalab/steeleagle/sdk/enums"
Actions:
    actions.TakeOff takeoff()
    actions.SetGimbalPose gimbal(Pose=types.Pose(Pitch=-30.0, Yaw=0.0, Roll=0.0), AngleMode=enums.AngleModeAbsolute)
Mission:
Start takeoff
During takeoff:
    done -> gimbal
