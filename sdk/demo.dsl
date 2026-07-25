Role Seeker:
Import:
    github.com/cmusatyalab/steeleagle_sdk/events
    github.com/cmusatyalab/steeleagle_sdk/actions
Data:
    Velocity vel(x_vel = 3.0, y_vel = 3.0, z_vel = 3.0, angular_vel = 120.0) # The Max velocity we are traveling at
    Waypoints patrol_path(alt = 15.0, area = PolyAnafi, algo = corridor, spacing = 15, angle_degrees = 17.0)
    Location hold_waypoint(latitude = 40.413619, longitude = -79.947277, altitude = 26.0)
    Location mission_start(latitude = 40.413551, longitude = -79.948432, altitude = 26.0)
    Location rth_first_waypoint(latitude = 40.4132426, longitude = -79.9462652, altitude = 26.0)
    Location rth_second_waypoint(latitude = 40.4130016, longitude = -79.9461965, altitude = 4.0)
    Detection aruco(class_name = aruco_0, score = 70)
    Detection person(class_name = person, score = 60)
    Pose pose(pitch = -45.0, yaw = 0.0, roll = 0.0) # Tracking angle for gimbal
    Pose pose_2(pitch = -90.0, yaw = 0.0, roll = 0.0)
Actions:
    TakeOff take_off(take_off_altitude = 3.0)
    Wait wait_1(duration = 30)
    Wait wait_2(duration = 15)
    Patrol patrol(waypoints = patrol_path)
    Track track(target = person, yaw_gain = 5.0, follow_speed = 0.0, descent_speed = 1.0, target_altitude = 10.0)
    SetGlobalPosition go_to_hold(location = hold_waypoint, heading_mode = 0, altitude_mode = 1)
    SetGlobalPosition go_to_hold_2(location = hold_waypoint, heading_mode = 0, altitude_mode = 1)
    SetGlobalPosition go_to_mission_start(location = mission_start, heading_mode = 0, altitude_mode = 1)
    SetGlobalPosition go_to_mission_start_2(location = mission_start, heading_mode = 0, altitude_mode = 1)
    SetGlobalPosition rth_phase_one(location = rth_first_waypoint, heading_mode = 0, altitude_mode = 1)
    SetGlobalPosition rth_phase_two(location = rth_second_waypoint, heading_mode = 0, altitude_mode = 1)
    ElevateToAltitude elevate(target_altitude = 26.0)
    SetGimbalPose set_gimbal_pose(gimbal_id = 0, pose = pose)
    SetGimbalPose set_land_pose(gimbal_id = 0, pose = pose_2)
    PrecisionLand precision_land(target = aruco, forward_speed = 0.5, lateral_speed = 0.5, descent_speed = 1.0, compute_stream = aruco_detector_engine, err_tol = 0.1, target_altitude = 2)
Events:
    DetectionFound person_seen(target = person)
    TimeReached timeout(duration = 30)
Mission:
    Start take_off
    During take_off:
        done -> elevate
    During elevate:
        done -> go_to_hold
    During go_to_hold:
        done -> wait_1
    During wait_1:
        done -> go_to_mission_start
    During go_to_mission_start:
        done -> set_gimbal_pose
    During set_gimbal_pose:
        done -> patrol
    During patrol:
        done -> patrol
        person_seen -> track
    During track:
        done -> go_to_mission_start_2
        timeout -> go_to_mission_start_2
    During go_to_mission_start_2:
        done -> go_to_hold_2
    During go_to_hold_2:
        done -> rth_phase_one
    During rth_phase_one:
        done -> rth_phase_two
    During rth_phase_two:
        done -> set_land_pose
    During set_land_pose:
        done -> wait_2
    During wait_2:
        done -> precision_land
