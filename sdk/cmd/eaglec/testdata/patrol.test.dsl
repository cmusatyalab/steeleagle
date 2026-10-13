Role Patroller:
Modules:
    "github.com/cmusatyalab/steeleagle/sdk" v4.0-beta
    "github.com/cmusatyalab/steeleagle/api/go" v4.0-beta
Imports:
    "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
    "github.com/cmusatyalab/steeleagle/sdk/dsl/datatypes"
    "github.com/cmusatyalab/steeleagle/sdk/params"
    "github.com/cmusatyalab/steeleagle/sdk/enums"
Actions:
    actions.TakeOff takeoff()
    actions.SetGimbalPose gimbal(Pose=datatypes.Pose(Pitch=-30.0, Yaw=0.0, Roll=0.0), AngleMode=enums.AngleModeAbsolute)
    actions.Patrol patrol(Altitude=15.0, Area=params.Poly, Speed=5.0)
Mission:
Start takeoff
During takeoff:
    done -> gimbal
During gimbal:
    done -> patrol
