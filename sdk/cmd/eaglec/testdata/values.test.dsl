Modules:
    "github.com/cmusatyalab/steeleagle/sdk" v4.0-beta => "../.."
Imports:
    "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
    dt "github.com/cmusatyalab/steeleagle/sdk/dsl/datatypes"
    "github.com/cmusatyalab/steeleagle/sdk/enums"
Data:
    dt.Pose down(Pitch=-90.0, Roll=0.0, Yaw=0.0)
Actions:
    actions.SetGimbalPose gimbal(Pose=down, AngleMode=enums.AngleModeAbsolute)
    actions.Wait wait(Duration=5, Tags=[1, 2.5, 'x'], Inner=dt.Pose(Pitch=1.0, Roll=2.0, Yaw=3.0), Note="hi")
Mission:
    Start gimbal
    During gimbal:
        done -> wait
