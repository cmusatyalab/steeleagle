Import:
    "github.com/cmusatyalab/steeleagle/sdk/dsl"
    "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
    "github.com/cmusatyalab/steeleagle/sdk/dsl/events"
    "github.com/cmusatyalab/steeleagle/sdk/dsl/types"
    "github.com/cmusatyalab/steeleagle/sdk/enums"

Data:
    Pose set_gimbal_pose_1_Pose(Pitch = -45, Roll = 0, Yaw = 0)

Actions:
    TakeOff take_off_1()
    SetGimbalPose set_gimbal_pose_1(Pose = set_gimbal_pose_1_Pose, AngleMode = AngleModeAbsolute, Frame = ReferenceFrameBody)
    Patrol patrol_1(SurveySpacing = 10, Speed = 3, AngularSpeed = 120, Altitude = 5, AltitudeMode = AltitudeModeRelative, Pattern = PatrolModeSurvey, SurveyHeading = 20, Area = "FieldB")
    ReturnToHome return_to_home_1()

Events:
    Battery battery_below_10(Comparator = LessOrEqual, Threshold = 10)

Mission:
    Start take_off_1
    During take_off_1:
        done -> set_gimbal_pose_1
    During set_gimbal_pose_1:
        done -> patrol_1
    During patrol_1:
        battery_below_10 -> return_to_home_1
