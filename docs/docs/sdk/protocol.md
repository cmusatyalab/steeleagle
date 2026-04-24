# Protocol Documentation
<a name="top"></a>

## Table of Contents

- [messages/result.proto](#messages_result-proto)
    - [AvoidanceResult](#steeleagle-protocol-messages-result-AvoidanceResult)
    - [BoundingBox](#steeleagle-protocol-messages-result-BoundingBox)
    - [ComputeResult](#steeleagle-protocol-messages-result-ComputeResult)
    - [Detection](#steeleagle-protocol-messages-result-Detection)
    - [DetectionResult](#steeleagle-protocol-messages-result-DetectionResult)
    - [FrameResult](#steeleagle-protocol-messages-result-FrameResult)
    - [HSV](#steeleagle-protocol-messages-result-HSV)
    - [SLAMResult](#steeleagle-protocol-messages-result-SLAMResult)

- [messages/telemetry.proto](#messages_telemetry-proto)
    - [AlertInfo](#steeleagle-protocol-messages-telemetry-AlertInfo)
    - [BatteryInfo](#steeleagle-protocol-messages-telemetry-BatteryInfo)
    - [CommsInfo](#steeleagle-protocol-messages-telemetry-CommsInfo)
    - [DriverTelemetry](#steeleagle-protocol-messages-telemetry-DriverTelemetry)
    - [Frame](#steeleagle-protocol-messages-telemetry-Frame)
    - [GPSInfo](#steeleagle-protocol-messages-telemetry-GPSInfo)
    - [GimbalInfo](#steeleagle-protocol-messages-telemetry-GimbalInfo)
    - [GimbalStatus](#steeleagle-protocol-messages-telemetry-GimbalStatus)
    - [ImagingSensorInfo](#steeleagle-protocol-messages-telemetry-ImagingSensorInfo)
    - [ImagingSensorStatus](#steeleagle-protocol-messages-telemetry-ImagingSensorStatus)
    - [ImagingSensorStreamStatus](#steeleagle-protocol-messages-telemetry-ImagingSensorStreamStatus)
    - [MissionInfo](#steeleagle-protocol-messages-telemetry-MissionInfo)
    - [MissionTelemetry](#steeleagle-protocol-messages-telemetry-MissionTelemetry)
    - [PositionInfo](#steeleagle-protocol-messages-telemetry-PositionInfo)
    - [SetpointInfo](#steeleagle-protocol-messages-telemetry-SetpointInfo)
    - [TelemetryStreamInfo](#steeleagle-protocol-messages-telemetry-TelemetryStreamInfo)
    - [VehicleInfo](#steeleagle-protocol-messages-telemetry-VehicleInfo)

    - [BatteryWarning](#steeleagle-protocol-messages-telemetry-BatteryWarning)
    - [CompassWarning](#steeleagle-protocol-messages-telemetry-CompassWarning)
    - [ConnectionWarning](#steeleagle-protocol-messages-telemetry-ConnectionWarning)
    - [GPSWarning](#steeleagle-protocol-messages-telemetry-GPSWarning)
    - [ImagingSensorType](#steeleagle-protocol-messages-telemetry-ImagingSensorType)
    - [MagnetometerWarning](#steeleagle-protocol-messages-telemetry-MagnetometerWarning)
    - [MissionExecState](#steeleagle-protocol-messages-telemetry-MissionExecState)
    - [MotionStatus](#steeleagle-protocol-messages-telemetry-MotionStatus)

- [services/compute_service.proto](#services_compute_service-proto)
    - [AddDatasinksRequest](#steeleagle-protocol-services-compute_service-AddDatasinksRequest)
    - [DatasinkInfo](#steeleagle-protocol-services-compute_service-DatasinkInfo)
    - [RemoveDatasinksRequest](#steeleagle-protocol-services-compute_service-RemoveDatasinksRequest)
    - [SetDatasinksRequest](#steeleagle-protocol-services-compute_service-SetDatasinksRequest)

    - [DatasinkLocation](#steeleagle-protocol-services-compute_service-DatasinkLocation)
    - [InputSource](#steeleagle-protocol-services-compute_service-InputSource)

    - [Compute](#steeleagle-protocol-services-compute_service-Compute)

- [services/control_service.proto](#services_control_service-proto)
    - [ArmRequest](#steeleagle-protocol-services-control_service-ArmRequest)
    - [ConfigureImagingSensorStreamRequest](#steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamRequest)
    - [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-control_service-ConfigureTelemetryStreamRequest)
    - [ConnectRequest](#steeleagle-protocol-services-control_service-ConnectRequest)
    - [DisarmRequest](#steeleagle-protocol-services-control_service-DisarmRequest)
    - [DisconnectRequest](#steeleagle-protocol-services-control_service-DisconnectRequest)
    - [HoldRequest](#steeleagle-protocol-services-control_service-HoldRequest)
    - [ImagingSensorConfiguration](#steeleagle-protocol-services-control_service-ImagingSensorConfiguration)
    - [JoystickRequest](#steeleagle-protocol-services-control_service-JoystickRequest)
    - [KillRequest](#steeleagle-protocol-services-control_service-KillRequest)
    - [LandRequest](#steeleagle-protocol-services-control_service-LandRequest)
    - [ReturnToHomeRequest](#steeleagle-protocol-services-control_service-ReturnToHomeRequest)
    - [SetGimbalPoseRequest](#steeleagle-protocol-services-control_service-SetGimbalPoseRequest)
    - [SetGimbalPoseTargetRequest](#steeleagle-protocol-services-control_service-SetGimbalPoseTargetRequest)
    - [SetGlobalPositionRequest](#steeleagle-protocol-services-control_service-SetGlobalPositionRequest)
    - [SetHeadingRequest](#steeleagle-protocol-services-control_service-SetHeadingRequest)
    - [SetHomeRequest](#steeleagle-protocol-services-control_service-SetHomeRequest)
    - [SetRelativePositionRequest](#steeleagle-protocol-services-control_service-SetRelativePositionRequest)
    - [SetVelocityRequest](#steeleagle-protocol-services-control_service-SetVelocityRequest)
    - [TakeOffRequest](#steeleagle-protocol-services-control_service-TakeOffRequest)

    - [AltitudeMode](#steeleagle-protocol-services-control_service-AltitudeMode)
    - [HeadingMode](#steeleagle-protocol-services-control_service-HeadingMode)
    - [PoseMode](#steeleagle-protocol-services-control_service-PoseMode)
    - [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame)

    - [Control](#steeleagle-protocol-services-control_service-Control)

- [services/flight_log_service.proto](#services_flight_log_service-proto)
    - [LogMessage](#steeleagle-protocol-services-flight_log_service-LogMessage)
    - [LogProtoRequest](#steeleagle-protocol-services-flight_log_service-LogProtoRequest)
    - [LogRequest](#steeleagle-protocol-services-flight_log_service-LogRequest)
    - [ReqRepProto](#steeleagle-protocol-services-flight_log_service-ReqRepProto)

    - [LogType](#steeleagle-protocol-services-flight_log_service-LogType)

    - [FlightLog](#steeleagle-protocol-services-flight_log_service-FlightLog)

- [services/mission_service.proto](#services_mission_service-proto)
    - [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamRequest)
    - [ConfigureTelemetryStreamResponse](#steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamResponse)
    - [MissionData](#steeleagle-protocol-services-mission_service-MissionData)
    - [NotifyRequest](#steeleagle-protocol-services-mission_service-NotifyRequest)
    - [StartRequest](#steeleagle-protocol-services-mission_service-StartRequest)
    - [StopRequest](#steeleagle-protocol-services-mission_service-StopRequest)
    - [UploadRequest](#steeleagle-protocol-services-mission_service-UploadRequest)

    - [Mission](#steeleagle-protocol-services-mission_service-Mission)

- [services/remote_service.proto](#services_remote_service-proto)
    - [CommandRequest](#steeleagle-protocol-services-remote_service-CommandRequest)
    - [CommandResponse](#steeleagle-protocol-services-remote_service-CommandResponse)
    - [CompileMissionRequest](#steeleagle-protocol-services-remote_service-CompileMissionRequest)
    - [CompileMissionResponse](#steeleagle-protocol-services-remote_service-CompileMissionResponse)

    - [Remote](#steeleagle-protocol-services-remote_service-Remote)

- [services/report_service.proto](#services_report_service-proto)
    - [ReportMessage](#steeleagle-protocol-services-report_service-ReportMessage)
    - [SendReportRequest](#steeleagle-protocol-services-report_service-SendReportRequest)

    - [Report](#steeleagle-protocol-services-report_service-Report)

- [testing/testing.proto](#testing_testing-proto)
    - [ServiceReady](#steeleagle-protocol-testing-ServiceReady)

    - [ServiceType](#steeleagle-protocol-testing-ServiceType)

- [Scalar Value Types](#scalar-value-types)



<a name="messages_result-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## messages/result.proto



<a name="steeleagle-protocol-messages-result-AvoidanceResult"></a>

### AvoidanceResult
Avoidance result generated by an avoidance model.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| actuation_vector | [double](#double) |  | actuation vector towards safe area |






<a name="steeleagle-protocol-messages-result-BoundingBox"></a>

### BoundingBox
Bounding box associated with an object detection.

Defines the upper left and lower right corners of a detected object
in an image frame. Origin (0,0) is the top left corner of the input image.
(image_height, image_width) is the bottom right corner.
Also the class and confidence threshold associated with the box.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| y_min | [double](#double) |  | minimum y offset percentage with respect to image size [0.0-1.0] |
| x_min | [double](#double) |  | minimum x offset percentage with respect to image size [0.0-1.0] |
| y_max | [double](#double) |  | maximum y offset percentage with respect to image size [0.0-1.0] |
| x_max | [double](#double) |  | maximum x offset percentage with respect to image size [0.0-1.0] |






<a name="steeleagle-protocol-messages-result-ComputeResult"></a>

### ComputeResult
Compute result generated by a compute server.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| engine_name | [string](#string) |  | engine that generated the result |
| detection_result | [DetectionResult](#steeleagle-protocol-messages-result-DetectionResult) |  | object detection |
| avoidance_result | [AvoidanceResult](#steeleagle-protocol-messages-result-AvoidanceResult) |  | avoidance directive |
| slam_result | [SLAMResult](#steeleagle-protocol-messages-result-SLAMResult) |  | SLAM position estimate |
| generic_result | [string](#string) |  | JSON result |






<a name="steeleagle-protocol-messages-result-Detection"></a>

### Detection
Object detection generated by a model.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| detection_id | [uint64](#uint64) |  | can be multiple objects per frame |
| class_name | [string](#string) |  | class name of detection |
| score | [double](#double) |  | confidence score |
| bbox | [BoundingBox](#steeleagle-protocol-messages-result-BoundingBox) |  | bounding box |






<a name="steeleagle-protocol-messages-result-DetectionResult"></a>

### DetectionResult
List of object detections.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| detections | [Detection](#steeleagle-protocol-messages-result-Detection) | repeated | list of detections |
| frame_id | [uint64](#uint64) |  | frame corresponding to these detections |






<a name="steeleagle-protocol-messages-result-FrameResult"></a>

### FrameResult
Compute results generated by datasink modules


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| type | [string](#string) |  | result type(s) |
| frame_id | [uint64](#uint64) |  | for correlation |
| result | [ComputeResult](#steeleagle-protocol-messages-result-ComputeResult) | repeated | list of generated results |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | inference timestamp |






<a name="steeleagle-protocol-messages-result-HSV"></a>

### HSV
HSV values generated by a color filter.

Color filter represented by hue, saturation, and value Uses OpenCV ranges defined [here](https://opencv.org/blog/color-spaces-in-opencv/).


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| h | [uint32](#uint32) |  | hue range is [0,179] |
| s | [uint32](#uint32) |  | saturation range is [0,255] |
| v | [uint32](#uint32) |  | value range is [0,255] |






<a name="steeleagle-protocol-messages-result-SLAMResult"></a>

### SLAMResult
SLAM result generated by a SLAM model.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| relative_position | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | relative position estimate relative to SLAM initialization |
| global_position | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | global position estimate |















<a name="messages_telemetry-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## messages/telemetry.proto



<a name="steeleagle-protocol-messages-telemetry-AlertInfo"></a>

### AlertInfo
Information about all vehicle warning and alerts.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| battery_warning | [BatteryWarning](#steeleagle-protocol-messages-telemetry-BatteryWarning) |  | battery warnings |
| gps_warning | [GPSWarning](#steeleagle-protocol-messages-telemetry-GPSWarning) |  | GPS warnings |
| magnetometer_warning | [MagnetometerWarning](#steeleagle-protocol-messages-telemetry-MagnetometerWarning) |  | magnetometer warnings |
| connection_warning | [ConnectionWarning](#steeleagle-protocol-messages-telemetry-ConnectionWarning) |  | connection warnings |
| compass_warning | [CompassWarning](#steeleagle-protocol-messages-telemetry-CompassWarning) |  | compass warnings |






<a name="steeleagle-protocol-messages-telemetry-BatteryInfo"></a>

### BatteryInfo
Information about the vehicle battery.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| percentage | [uint32](#uint32) |  | battery level [0-100]% |






<a name="steeleagle-protocol-messages-telemetry-CommsInfo"></a>

### CommsInfo
Future: information about the vehicle&#39;s communication links.






<a name="steeleagle-protocol-messages-telemetry-DriverTelemetry"></a>

### DriverTelemetry
Telemetry message for the vehicle, originating from the driver module.

This message outlines all the current information about the vehicle. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | timestamp of message |
| telemetry_stream_info | [TelemetryStreamInfo](#steeleagle-protocol-messages-telemetry-TelemetryStreamInfo) |  | info about current telemetry stream |
| vehicle_info | [VehicleInfo](#steeleagle-protocol-messages-telemetry-VehicleInfo) |  | the vehicle that this telemetry corresponds to |
| position_info | [PositionInfo](#steeleagle-protocol-messages-telemetry-PositionInfo) |  | positional info about the vehicle |
| gimbal_info | [GimbalInfo](#steeleagle-protocol-messages-telemetry-GimbalInfo) |  | status on attached gimbals and their orientations |
| imaging_sensor_info | [ImagingSensorInfo](#steeleagle-protocol-messages-telemetry-ImagingSensorInfo) |  | information about the vehicle imaging sensors |
| alert_info | [AlertInfo](#steeleagle-protocol-messages-telemetry-AlertInfo) |  | enumeration of vehicle warnings |






<a name="steeleagle-protocol-messages-telemetry-Frame"></a>

### Frame
Imaging sensor frames, originating from the driver module.

This message provides frame data from currently streaming imaging sensors. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | capture timestamp of the frame |
| data | [bytes](#bytes) |  | raw bytes representing the frame |
| h_res | [uint64](#uint64) |  | horizontal frame resolution in pixels |
| v_res | [uint64](#uint64) |  | vertical frame resolution in pixels |
| d_res | [uint64](#uint64) |  | depth resolution in pixels |
| channels | [uint64](#uint64) |  | number of channels |
| id | [uint64](#uint64) |  | frame ID for future correlation |
| vehicle_info | [VehicleInfo](#steeleagle-protocol-messages-telemetry-VehicleInfo) |  | the vehicle that this telemetry corresponds to |
| position_info | [PositionInfo](#steeleagle-protocol-messages-telemetry-PositionInfo) |  | positional info about the vehicle |
| gimbal_info | [GimbalInfo](#steeleagle-protocol-messages-telemetry-GimbalInfo) |  | status on attached gimbals and their orientations |
| imaging_sensor_info | [ImagingSensorInfo](#steeleagle-protocol-messages-telemetry-ImagingSensorInfo) |  | information about the vehicle imaging sensors |






<a name="steeleagle-protocol-messages-telemetry-GPSInfo"></a>

### GPSInfo
Information about the vehicle GPS fix.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| satellites | [uint32](#uint32) |  | number of satellites used in GPS fix |






<a name="steeleagle-protocol-messages-telemetry-GimbalInfo"></a>

### GimbalInfo
Info of all attached gimbals.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| num_gimbals | [uint32](#uint32) |  | number of connected gimbals |
| gimbals | [GimbalStatus](#steeleagle-protocol-messages-telemetry-GimbalStatus) | repeated | list of connected gimbals |






<a name="steeleagle-protocol-messages-telemetry-GimbalStatus"></a>

### GimbalStatus
Status of a gimbal.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| id | [uint32](#uint32) |  | ID of the gimbal |
| pose_body | [steeleagle.protocol.common.Pose](#steeleagle-protocol-common-Pose) |  | current pose in the body (forward, right, up) reference frame |
| pose_neu | [steeleagle.protocol.common.Pose](#steeleagle-protocol-common-Pose) |  | current pose in the NEU (North, East, Up) reference frame |






<a name="steeleagle-protocol-messages-telemetry-ImagingSensorInfo"></a>

### ImagingSensorInfo
Information about all attached imaging sensors.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| stream_status | [ImagingSensorStreamStatus](#steeleagle-protocol-messages-telemetry-ImagingSensorStreamStatus) |  | status of current imaging sensor streams |
| sensors | [ImagingSensorStatus](#steeleagle-protocol-messages-telemetry-ImagingSensorStatus) | repeated | list of connected imaging sensors |






<a name="steeleagle-protocol-messages-telemetry-ImagingSensorStatus"></a>

### ImagingSensorStatus
Status of an imaging sensor.

Includes information about its type and resolution/stream settings.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| id | [uint32](#uint32) |  | ID of the imaging sensor |
| type | [ImagingSensorType](#steeleagle-protocol-messages-telemetry-ImagingSensorType) |  | type of the imaging sensor |
| active | [bool](#bool) |  | indicates whether the imaging sensor is currently streaming |
| supports_secondary | [bool](#bool) |  | indicates whether the imaging sensor supports background streaming |
| current_fps | [uint32](#uint32) |  | current streaming frames per second |
| max_fps | [uint32](#uint32) |  | maximum streaming frames per second |
| h_res | [uint32](#uint32) |  | horizontal resolution |
| v_res | [uint32](#uint32) |  | vertical resolution |
| channels | [uint32](#uint32) |  | number of image channels |
| h_fov | [uint32](#uint32) |  | horizontal FOV |
| v_fov | [uint32](#uint32) |  | vertical FOV |
| gimbal_mounted | [bool](#bool) |  | indicates if imaging sensor is gimbal mounted |
| gimbal_id | [uint32](#uint32) |  | indicates which gimbal the imaging sensor is mounted on |






<a name="steeleagle-protocol-messages-telemetry-ImagingSensorStreamStatus"></a>

### ImagingSensorStreamStatus
Information about all imaging sensor streams.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| stream_capacity | [uint32](#uint32) |  | the total number of allowed simultaneously streaming cameras |
| num_streams | [uint32](#uint32) |  | the total number of currently streaming cameras |
| primary_cam | [uint32](#uint32) |  | ID of the primary camera |
| secondary_cams | [uint32](#uint32) | repeated | IDs of the secondary active cameras |






<a name="steeleagle-protocol-messages-telemetry-MissionInfo"></a>

### MissionInfo
Information about the current mission.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| name | [string](#string) |  | mission name |
| hash | [int64](#int64) |  | mission hash to establish version uniqueness |
| age | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | timestamp of upload |
| exec_state | [MissionExecState](#steeleagle-protocol-messages-telemetry-MissionExecState) |  | execution state of the mission |
| task_state | [string](#string) |  | task state of the mission (plaintext), if active |






<a name="steeleagle-protocol-messages-telemetry-MissionTelemetry"></a>

### MissionTelemetry
Telemetry message for the mission, originating from the mission module.

This message outlines all current information about the mission. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | timestamp of message |
| telemetry_stream_info | [TelemetryStreamInfo](#steeleagle-protocol-messages-telemetry-TelemetryStreamInfo) |  | info about the current telemetry stream |
| mission_info | [MissionInfo](#steeleagle-protocol-messages-telemetry-MissionInfo) | repeated | info about the current mission states |






<a name="steeleagle-protocol-messages-telemetry-PositionInfo"></a>

### PositionInfo
Information about the vehicle position.

Includes home position, global position (only valid with a GPS fix), relative position (only available on some vehicles), current velocity, and the current setpoint.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| home | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | global position that will be used when returning home |
| global_position | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | current global position of the vehicle |
| relative_position | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | current local position of the vehicle in the global NEU (North, East, Up) coordinate frame, relative to start position |
| velocity_neu | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | current velocity of the vehicle in the global NEU (North, East, Up) coordinate frame |
| velocity_body | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | current velocity of the vehicle in the body (forward, right, up) coordinate frame |
| setpoint_info | [SetpointInfo](#steeleagle-protocol-messages-telemetry-SetpointInfo) |  | info on the current vehicle setpoint |






<a name="steeleagle-protocol-messages-telemetry-SetpointInfo"></a>

### SetpointInfo
Information about the current setpoint.

Provides the current setpoint for the vehicle. A setpoint is a position or velocity target
that the vehicle is currently moving towards. By default, when the vehicle is idle, this
setpoint is a `position_body_sp` object set to all zeros. The frame of reference for each
setpoint is implied by the name; e.g. velocity_neu_sp uses the NEU (North, East, Up)
reference frame and velocity_body_sp uses the body (forward, right, up) reference frame.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| position_body_sp | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | default all zeros idle setpoint |
| position_neu_sp | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | NEU (North, East, Up) position setpoint |
| global_sp | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | global setpoint |
| velocity_body_sp | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | body (forward, right, up) velocity setpoint |
| velocity_neu_sp | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | NEU (North, East, Up) velocity setpoint |






<a name="steeleagle-protocol-messages-telemetry-TelemetryStreamInfo"></a>

### TelemetryStreamInfo
Information about the telemetry stream.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| current_frequency | [uint32](#uint32) |  | current frequency of telemetry messages [Hz] |
| max_frequency | [uint32](#uint32) |  | maximum frequency of telemetry messages [Hz] |
| uptime | [google.protobuf.Duration](#google-protobuf-Duration) |  | uptime of the stream |






<a name="steeleagle-protocol-messages-telemetry-VehicleInfo"></a>

### VehicleInfo
Information about the vehicle.

This includes the name, make, model and its current status (battery, GPS, comms, motion).


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| name | [string](#string) |  | the vehicle that this telemetry corresponds to |
| model | [string](#string) |  | model of the vehicle |
| manufacturer | [string](#string) |  | manufacturer of the vehicle |
| motion_status | [MotionStatus](#steeleagle-protocol-messages-telemetry-MotionStatus) |  | current status of the vehicle |
| battery_info | [BatteryInfo](#steeleagle-protocol-messages-telemetry-BatteryInfo) |  | battery info for the vehicle |
| gps_info | [GPSInfo](#steeleagle-protocol-messages-telemetry-GPSInfo) |  | GPS sensor info for the vehicle |
| comms_info | [CommsInfo](#steeleagle-protocol-messages-telemetry-CommsInfo) |  | communications info for the vehicle |








<a name="steeleagle-protocol-messages-telemetry-BatteryWarning"></a>

### BatteryWarning
Battery warnings and alerts.

| Name | Number | Description |
| ---- | ------ | ----------- |
| NONE | 0 | the vehicle is above 30% battery |
| LOW | 1 | the vehicle is below 30% battery |
| CRITICAL | 2 | the vehicle is below 15% battery |



<a name="steeleagle-protocol-messages-telemetry-CompassWarning"></a>

### CompassWarning
Compass warnings and alerts.

| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_COMPASS_WARNING | 0 | absolute heading is nominal |
| WEAK_HEADING_LOCK | 1 | absolute heading is available but may be incorrect |
| NO_HEADING_LOCK | 2 | no absolute heading available from the vehicle |



<a name="steeleagle-protocol-messages-telemetry-ConnectionWarning"></a>

### ConnectionWarning
Connection warnings and alerts.

| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_CONNECTION_WARNING | 0 | connection to remote server is nominal |
| DISCONNECTED | 1 | contact has been lost with the remote server |
| WEAK_CONNECTION | 2 | connection is experiencing interference or is weak |



<a name="steeleagle-protocol-messages-telemetry-GPSWarning"></a>

### GPSWarning
GPS fix warnings and alerts.

| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_GPS_WARNING | 0 | GPS readings are nominal and a fix has been achieved |
| WEAK_SIGNAL | 1 | weak GPS fix, expect errant global position data |
| NO_FIX | 2 | no GPS fix |



<a name="steeleagle-protocol-messages-telemetry-ImagingSensorType"></a>

### ImagingSensorType
Imaging sensor types.

| Name | Number | Description |
| ---- | ------ | ----------- |
| RGB | 0 | RGB camera |
| STEREO | 1 | stereo camera |
| THERMAL | 2 | thermal camera |
| NIGHT | 3 | night vision camera |
| LIDAR | 4 | LIDAR sensor |
| RGBD | 5 | RGB-Depth camera |
| TOF | 6 | ToF (time of flight) camera |
| RADAR | 7 | RADAR sensor |



<a name="steeleagle-protocol-messages-telemetry-MagnetometerWarning"></a>

### MagnetometerWarning
Magnetometer warnings and alerts.

| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_MAGNETOMETER_WARNING | 0 | magnetometer readings are nominal |
| PERTURBATION | 1 | the vehicle is experiencing magnetic perturbations |



<a name="steeleagle-protocol-messages-telemetry-MissionExecState"></a>

### MissionExecState
Execution state of the current mission.

| Name | Number | Description |
| ---- | ------ | ----------- |
| READY | 0 | mission is ready to be executed |
| IN_PROGRESS | 1 | mission is in progress |
| PAUSED | 3 | mission is paused |
| COMPLETED | 4 | mission has been completed |
| CANCELED | 5 | mission was cancelled |



<a name="steeleagle-protocol-messages-telemetry-MotionStatus"></a>

### MotionStatus
Information about the motion of the vehicle.

| Name | Number | Description |
| ---- | ------ | ----------- |
| MOTORS_OFF | 0 | motors of the vehicle are off |
| RAMPING_UP | 1 | motors of the vehicle are ramping |
| IDLE | 2 | the vehicle is on but idle |
| IN_TRANSIT | 3 | the vehicle is in motion |
| RAMPING_DOWN | 4 | motors of the vehicle are ramping down |










<a name="services_compute_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/compute_service.proto



<a name="steeleagle-protocol-services-compute_service-AddDatasinksRequest"></a>

### AddDatasinksRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| datasinks | [DatasinkInfo](#steeleagle-protocol-services-compute_service-DatasinkInfo) | repeated | name of target datasinks |






<a name="steeleagle-protocol-services-compute_service-DatasinkInfo"></a>

### DatasinkInfo
Information about a datasink.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| id | [string](#string) |  | datasink ID |
| location | [DatasinkLocation](#steeleagle-protocol-services-compute_service-DatasinkLocation) |  | datasink location |
| sources | [InputSource](#steeleagle-protocol-services-compute_service-InputSource) | repeated | input sources for this datasink |






<a name="steeleagle-protocol-services-compute_service-RemoveDatasinksRequest"></a>

### RemoveDatasinksRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| datasinks | [DatasinkInfo](#steeleagle-protocol-services-compute_service-DatasinkInfo) | repeated | name of target datasinks |






<a name="steeleagle-protocol-services-compute_service-SetDatasinksRequest"></a>

### SetDatasinksRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| datasinks | [DatasinkInfo](#steeleagle-protocol-services-compute_service-DatasinkInfo) | repeated | name of target datasinks |








<a name="steeleagle-protocol-services-compute_service-DatasinkLocation"></a>

### DatasinkLocation
Denotes where a datasink is located.

| Name | Number | Description |
| ---- | ------ | ----------- |
| REMOTE | 0 | remote location (network hop required) |
| LOCAL | 1 | local location (IPC) |



<a name="steeleagle-protocol-services-compute_service-InputSource"></a>

### InputSource


| Name | Number | Description |
| ---- | ------ | ----------- |
| SOURCE_UNSPECIFIED | 0 | default value |
| DRIVER_TELEMETRY | 1 | telemetry from the vehicle driver |
| MISSION_TELEMETRY | 2 | telemetry from the mission service |
| IMAGERY | 3 | imagery from the vehicle |







<a name="steeleagle-protocol-services-compute_service-Compute"></a>

### Compute
Used to configure datasinks for sensor streams.

This service is used to configure datasink endpoints for frames and
telemetry post-processing. It maintains an internal consumer list of
datasinks that the kernel broadcasts frames and telemetry to. RPC
methods within this service allow for manipulation of this list.

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| AddDatasinks | [AddDatasinksRequest](#steeleagle-protocol-services-compute_service-AddDatasinksRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Add datasinks to consumer list. Takes a list of datasinks and adds them to the current consumer list. |
| SetDatasinks | [SetDatasinksRequest](#steeleagle-protocol-services-compute_service-SetDatasinksRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Set the datasink consumer list. Takes a list of datasinks and replaces the current consumer list with them. |
| RemoveDatasinks | [RemoveDatasinksRequest](#steeleagle-protocol-services-compute_service-RemoveDatasinksRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Remove datasinks from consumer list. Takes a list of datasinks and removes them from the current consumer list. |





<a name="services_control_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/control_service.proto



<a name="steeleagle-protocol-services-control_service-ArmRequest"></a>

### ArmRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamRequest"></a>

### ConfigureImagingSensorStreamRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| configurations | [ImagingSensorConfiguration](#steeleagle-protocol-services-control_service-ImagingSensorConfiguration) | repeated | list of configurations to be updated |






<a name="steeleagle-protocol-services-control_service-ConfigureTelemetryStreamRequest"></a>

### ConfigureTelemetryStreamRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| frequency | [uint32](#uint32) |  | target frequency of telemetry generation, in Hz |






<a name="steeleagle-protocol-services-control_service-ConnectRequest"></a>

### ConnectRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-DisarmRequest"></a>

### DisarmRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-DisconnectRequest"></a>

### DisconnectRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-HoldRequest"></a>

### HoldRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-ImagingSensorConfiguration"></a>

### ImagingSensorConfiguration
Configuration for an imaging sensor.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| id | [uint32](#uint32) |  | target imaging sensor ID |
| set_primary | [bool](#bool) |  | set this sensor as the primary stream |
| set_fps | [uint32](#uint32) |  | target FPS for stream |






<a name="steeleagle-protocol-services-control_service-JoystickRequest"></a>

### JoystickRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| velocity | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | target velocity to move towards |
| duration | [google.protobuf.Duration](#google-protobuf-Duration) |  | time of actuation after which the vehicle will Hold |






<a name="steeleagle-protocol-services-control_service-KillRequest"></a>

### KillRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-LandRequest"></a>

### LandRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-ReturnToHomeRequest"></a>

### ReturnToHomeRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |






<a name="steeleagle-protocol-services-control_service-SetGimbalPoseRequest"></a>

### SetGimbalPoseRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| gimbal_id | [uint32](#uint32) |  | ID of the target gimbal |
| pose | [steeleagle.protocol.common.Pose](#steeleagle-protocol-common-Pose) |  | target pose |
| pose_mode | [PoseMode](#steeleagle-protocol-services-control_service-PoseMode) | optional | specifies how to interpret the target pose |
| frame | [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame) | optional | frame of reference |






<a name="steeleagle-protocol-services-control_service-SetGimbalPoseTargetRequest"></a>

### SetGimbalPoseTargetRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| gimbal_id | [uint32](#uint32) |  | ID of the target gimbal |
| pose | [steeleagle.protocol.common.Pose](#steeleagle-protocol-common-Pose) |  | target pose |
| pose_mode | [PoseMode](#steeleagle-protocol-services-control_service-PoseMode) | optional | specifies how to interpret the target pose |
| frame | [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame) | optional | frame of reference |






<a name="steeleagle-protocol-services-control_service-SetGlobalPositionRequest"></a>

### SetGlobalPositionRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| location | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | target global position |
| heading_mode | [HeadingMode](#steeleagle-protocol-services-control_service-HeadingMode) | optional | determines how the vehicle will orient during transit (default: `TO_TARGET`) |
| altitude_mode | [AltitudeMode](#steeleagle-protocol-services-control_service-AltitudeMode) | optional | determines how the vehicle will interpret altitude (default: `ABSOLUTE`) |
| max_velocity | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) | optional | maximum velocity during transit |






<a name="steeleagle-protocol-services-control_service-SetHeadingRequest"></a>

### SetHeadingRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| location | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | target heading or global location to look at |
| heading_mode | [HeadingMode](#steeleagle-protocol-services-control_service-HeadingMode) | optional | determines how the drone will orient |






<a name="steeleagle-protocol-services-control_service-SetHomeRequest"></a>

### SetHomeRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| location | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | new home location |






<a name="steeleagle-protocol-services-control_service-SetRelativePositionRequest"></a>

### SetRelativePositionRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| position | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | target relative position |
| max_velocity | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) | optional | maximum velocity during transit |
| frame | [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame) | optional | frame of reference |






<a name="steeleagle-protocol-services-control_service-SetVelocityRequest"></a>

### SetVelocityRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| velocity | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | target velocity |
| frame | [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame) | optional | frame of reference |






<a name="steeleagle-protocol-services-control_service-TakeOffRequest"></a>

### TakeOffRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| take_off_altitude | [float](#float) |  | take off height in relative altitude [meters] |








<a name="steeleagle-protocol-services-control_service-AltitudeMode"></a>

### AltitudeMode
Altitude mode switch.

| Name | Number | Description |
| ---- | ------ | ----------- |
| ABSOLUTE | 0 | meters above Mean Sea Level |
| RELATIVE | 1 | meters above takeoff position |



<a name="steeleagle-protocol-services-control_service-HeadingMode"></a>

### HeadingMode
Heading mode switch.

| Name | Number | Description |
| ---- | ------ | ----------- |
| TO_TARGET | 0 | orient towards the target location |
| HEADING_START | 1 | orient towards the given heading |



<a name="steeleagle-protocol-services-control_service-PoseMode"></a>

### PoseMode
Pose mode switch.

| Name | Number | Description |
| ---- | ------ | ----------- |
| ANGLE | 0 | absolute angle |
| OFFSET | 1 | request data // Offset from current |
| VELOCITY | 2 | rotational velocities |



<a name="steeleagle-protocol-services-control_service-ReferenceFrame"></a>

### ReferenceFrame
Reference frame mode switch.

| Name | Number | Description |
| ---- | ------ | ----------- |
| BODY | 0 | vehicle reference frame |
| NEU | 1 | NEU (North, East, Up) reference frame |







<a name="steeleagle-protocol-services-control_service-Control"></a>

### Control
Used for low-level control of a vehicle.

This service is hosted by the driver module and represents the global
control interface for the vehicle. Most methods called here will result
in actuation of the vehicle if it is armed (be careful!). Some methods,
like TakeOff, may take some time to complete. For this reason, it is
not advisable to set a timeout/deadline on the RPC call. However, to
ensure that the service is progressing, a client can either check
telemetry or listen for `IN_PROGRESS` response heartbeats which are
streamed back from the RPC while executing an operation.

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| Connect | [ConnectRequest](#steeleagle-protocol-services-control_service-ConnectRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Connect to the vehicle. Connects to the underlying vehicle hardware. Generally, this method is called by the law authority on startup and is not called by user code. |
| Disconnect | [DisconnectRequest](#steeleagle-protocol-services-control_service-DisconnectRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Disconnect from the vehicle. Disconnects from the underlying vehicle hardware. Generally, this method is called by the law authority when it attempts a driver restart and is not called by user code. |
| Arm | [ArmRequest](#steeleagle-protocol-services-control_service-ArmRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Order the vehicle to arm. Arms the vehicle. This is required before any other commands are run, otherwise the methods will return `FAILED_PRECONDITION`. Once the vehicle is armed, all subsequent actuation methods _will move the vehicle_. Make sure to go over the manufacturer recommended vehicle-specific pre-operation checklist before arming. |
| Disarm | [DisarmRequest](#steeleagle-protocol-services-control_service-DisarmRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Order the vehicle to disarm. Disarms the vehicle. Prevents any further actuation methods from executing, unless the vehicle is re-armed. |
| Joystick | [JoystickRequest](#steeleagle-protocol-services-control_service-JoystickRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Send a joystick command to the vehicle. Causes the vehicle to accelerate towards a provided velocity setpoint over a provided duration. This is useful for fine-grained control based on streamed datasink results or for tele-operating the vehicle from a remote commander. |
| TakeOff | [TakeOffRequest](#steeleagle-protocol-services-control_service-TakeOffRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to take off. Causes the vehicle to take off to a specified take off altitude. If the vehicle is not a UAV, this method will be unimplemented. |
| Land | [LandRequest](#steeleagle-protocol-services-control_service-LandRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to land. Causes the vehicle to land at its current location. If the vehicle is not a UAV, this method will be unimplemented. |
| Hold | [HoldRequest](#steeleagle-protocol-services-control_service-HoldRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to hold/loiter. Causes the vehicle to hold at its current location and to cancel any ongoing movement commands (`ReturnToHome` e.g.). |
| Kill | [KillRequest](#steeleagle-protocol-services-control_service-KillRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Orders an emergency shutdown of the vehicle motors. Causes the vehicle to immediately turn off its motors. _If the vehicle is a UAV, this will result in a freefall_. Use this method only in emergency situations. |
| SetHome | [SetHomeRequest](#steeleagle-protocol-services-control_service-SetHomeRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Set the home location of the vehicle. Changes the home location of the vehicle. Future `ReturnToHome` commands will move the vehicle to the provided location instead of its starting position. |
| ReturnToHome | [ReturnToHomeRequest](#steeleagle-protocol-services-control_service-ReturnToHomeRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to return to its home position. Causes the vehicle to return to its home position. If the home position has not been explicitly set, this will be its start position (defined as its takeoff position for UAVs). If the home position has been explicitly set, by `SetHome`, the vehicle will return to that position instead. |
| SetGlobalPosition | [SetGlobalPositionRequest](#steeleagle-protocol-services-control_service-SetGlobalPositionRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to move to a global position. Causes the vehicle to transit to the provided global position. The vehicle will interpret the heading of travel according to `heading_mode`: - `TO_TARGET` -&gt; turn to face the target position bearing - `HEADING_START` -&gt; turn to face the provided heading in the global position object. This will be the heading the vehicle maintains for the duration of transit. Generally only UAVs will support `HEADING_START`. The vehicle will move towards the target at the specified maximum velocity until the vehicle has reached its destination. Error tolerance is determined by the driver. Maximum velocity is interpreted from `max_velocity` as follows: - `x_vel` -&gt; maximum _horizontal_ velocity - `y_vel` -&gt; ignored - `z_vel` -&gt; maximum _vertical_ velocity _(UAV only)_ If no maximum velocity is provided, the driver will use a preset speed usually determined by the manufacturer or hardware settings. _(UAV only)_ During motion, the vehicle will also ascend or descend towards the target altitude, linearly interpolating this movement over the duration of travel. The vehicle will interpret altitude from `altitude_mode` as follows: - `ABSOLUTE` -&gt; altitude is relative to MSL (Mean Sea Level) - `RELATIVE` -&gt; altitude is relative to take off position |
| SetRelativePosition | [SetRelativePositionRequest](#steeleagle-protocol-services-control_service-SetRelativePositionRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to move to a relative position. Causes the vehicle to transit to the provided relative position. The vehicle will interpret the input position according to `frame` as follows: - `BODY` -&gt; (`x`, `y`, `z`) = (forward offset, right offset, up offset) _from current position_ - `NEU` -&gt; (`x`, `y`, `z`) = (north offset, east offset, up offset) _from start position_ The vehicle will move towards the target at the specified maximum velocity until the vehicle has reached its destination. Error tolerance is determined by the driver. Maximum velocity is interpreted from `max_velocity` as follows: - `x_vel` -&gt; maximum _horizontal_ velocity - `y_vel` -&gt; ignored - `z_vel` -&gt; maximum _vertical_ velocity _(UAV only)_ If no maximum velocity is provided, the driver will use a preset speed usually determined by the manufacturer or hardware settings. |
| SetVelocity | [SetVelocityRequest](#steeleagle-protocol-services-control_service-SetVelocityRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to accelerate to a velocity. Causes the vehicle to accelerate until it reaches a provided velocity. Error tolerance is determined by the driver. The vehicle will interpret the input velocity according to `frame` as follows: - `BODY` -&gt; (`x_vel`, `y_vel`, `z_vel`) = (forward velocity, right velocity, up velocity) - `NEU` -&gt; (`x_vel`, `y_vel`, `z_vel`) = (north velocity, east velocity, up velocity) |
| SetHeading | [SetHeadingRequest](#steeleagle-protocol-services-control_service-SetHeadingRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to set a new heading. Causes the vehicle to turn to face the provided global position. The vehicle will interpret the final heading according to `heading_mode`: - `TO_TARGET` -&gt; turn to face the target position bearing - `HEADING_START` -&gt; turn to face the provided heading in the global position object. |
| SetGimbalPose | [SetGimbalPoseRequest](#steeleagle-protocol-services-control_service-SetGimbalPoseRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Order the vehicle to set the pose of a gimbal. Causes the vehicle to actuate a gimbal to a new pose. The vehicle will interpret the new pose type from `pose_mode` as follows: - `ABSOLUTE` -&gt; absolute angle - `RELATIVE` -&gt; angle relative to current position - `VELOCITY` -&gt; angular velocities The vehicle will interpret the new pose angles according to `frame` as follows: - `BODY` -&gt; (`pitch`, `roll`, `yaw`) = (body pitch, body roll, body yaw) - `NEU` -&gt; (`pitch`, `roll`, `yaw`) = (body pitch, body roll, global yaw) |
| SetGimbalPoseTarget | [SetGimbalPoseTargetRequest](#steeleagle-protocol-services-control_service-SetGimbalPoseTargetRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Order the vehicle to set the pose of a gimbal asynchronously. Causes the vehicle to actuate a gimbal to a new pose. The vehicle will interpret the new pose type from `pose_mode` as follows: - `ABSOLUTE` -&gt; absolute angle - `RELATIVE` -&gt; angle relative to current position - `VELOCITY` -&gt; angular velocities The vehicle will interpret the new pose angles according to `frame` as follows: - `BODY` -&gt; (`pitch`, `roll`, `yaw`) = (body pitch, body roll, body yaw) - `NEU` -&gt; (`pitch`, `roll`, `yaw`) = (body pitch, body roll, global yaw) |
| ConfigureImagingSensorStream | [ConfigureImagingSensorStreamRequest](#steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Configure the vehicle imaging stream. Sets which imaging sensors are streaming and sets their target frame rates. |
| ConfigureTelemetryStream | [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-control_service-ConfigureTelemetryStreamRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Configure the vehicle telemetry stream. Sets the frequency of the telemetry stream. |





<a name="services_flight_log_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/flight_log_service.proto



<a name="steeleagle-protocol-services-flight_log_service-LogMessage"></a>

### LogMessage
Basic log message.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| type | [LogType](#steeleagle-protocol-services-flight_log_service-LogType) |  | type of the log |
| msg | [string](#string) |  | message content |






<a name="steeleagle-protocol-services-flight_log_service-LogProtoRequest"></a>

### LogProtoRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| topic | [string](#string) |  | topic of the log |
| reqrep_proto | [ReqRepProto](#steeleagle-protocol-services-flight_log_service-ReqRepProto) |  | Request/Response object and content |






<a name="steeleagle-protocol-services-flight_log_service-LogRequest"></a>

### LogRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| topic | [string](#string) |  | topic of the log |
| log | [LogMessage](#steeleagle-protocol-services-flight_log_service-LogMessage) |  | log content |






<a name="steeleagle-protocol-services-flight_log_service-ReqRepProto"></a>

### ReqRepProto
Protobuf object that is either a Request/Response type.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  | response data |
| name | [string](#string) |  | name of the request and associated service |
| content | [string](#string) |  | plaintext representation of the proto contents (usually via MessageToDict) |








<a name="steeleagle-protocol-services-flight_log_service-LogType"></a>

### LogType
Log types (follows Python convention).

| Name | Number | Description |
| ---- | ------ | ----------- |
| DEBUG | 0 | for debugging |
| INFO | 1 | information |
| PROTO | 2 | Protobuf objects |
| WARNING | 3 | warnings |
| ERROR | 4 | errors |
| CRITICAL | 5 | critical errors |







<a name="steeleagle-protocol-services-flight_log_service-FlightLog"></a>

### FlightLog
Used to log to a flight log.

This service is hosted by a logger instance and is responsible
for writing all system logs to an MCAP file for mission playback.

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| Log | [LogRequest](#steeleagle-protocol-services-flight_log_service-LogRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Basic log endpoint. Behaves identically to most log endpoints, but writes the data to an MCAP file instead of the console. |
| LogProto | [LogProtoRequest](#steeleagle-protocol-services-flight_log_service-LogProtoRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Protobuf log endpoint. Accepts Protobuf Request/Response types, and writes the data to an MCAP file. Useful for playback of gRPC calls. |





<a name="services_mission_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/mission_service.proto



<a name="steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamRequest"></a>

### ConfigureTelemetryStreamRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| frequency | [uint32](#uint32) |  | Target frequency for telemetry stream |






<a name="steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamResponse"></a>

### ConfigureTelemetryStreamResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-mission_service-MissionData"></a>

### MissionData



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| content | [string](#string) |  | URI, either local or remote, of a mission file |
| map | [bytes](#bytes) |  | kml object |






<a name="steeleagle-protocol-services-mission_service-NotifyRequest"></a>

### NotifyRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| notify_code | [int32](#int32) |  | Integer notification code, generated by the backend |






<a name="steeleagle-protocol-services-mission_service-StartRequest"></a>

### StartRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-mission_service-StopRequest"></a>

### StopRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-mission_service-UploadRequest"></a>

### UploadRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| mission | [MissionData](#steeleagle-protocol-services-mission_service-MissionData) |  | Data of the target mission |












<a name="steeleagle-protocol-services-mission_service-Mission"></a>

### Mission
Used to start a new mission or stop an active mission

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| Upload | [UploadRequest](#steeleagle-protocol-services-mission_service-UploadRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Upload a mission for execution |
| Start | [StartRequest](#steeleagle-protocol-services-mission_service-StartRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Start an uploaded mission |
| Stop | [StopRequest](#steeleagle-protocol-services-mission_service-StopRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Stop the current mission |
| Notify | [NotifyRequest](#steeleagle-protocol-services-mission_service-NotifyRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Send a notification to the current mission |
| ConfigureTelemetryStream | [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Set the mission telemetry stream parameters |





<a name="services_remote_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/remote_service.proto



<a name="steeleagle-protocol-services-remote_service-CommandRequest"></a>

### CommandRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| sequence_number | [uint32](#uint32) | optional | Since command sequencing is not built-in to ZeroMQ, it must be done manually; this will be set automatically by the server |
| request | [google.protobuf.Any](#google-protobuf-Any) |  | Contains request data for an RPC call |
| method_name | [string](#string) |  | Fully qualified method name |
| identity | [string](#string) |  | Identity of the sender |
| vehicle_id | [string](#string) |  | Target vehicle to send to |






<a name="steeleagle-protocol-services-remote_service-CommandResponse"></a>

### CommandResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| sequence_number | [uint32](#uint32) |  | This response is not seen by the client, but is a wrapper around a normal response; this is done for sequence_number correlation |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  | Generic response |






<a name="steeleagle-protocol-services-remote_service-CompileMissionRequest"></a>

### CompileMissionRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| dsl_content | [string](#string) |  |  |






<a name="steeleagle-protocol-services-remote_service-CompileMissionResponse"></a>

### CompileMissionResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| compiled_dsl_content | [string](#string) |  |  |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |












<a name="steeleagle-protocol-services-remote_service-Remote"></a>

### Remote
Used to control a vehicle remotely over ZeroMQ, usually hosted
on the server

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| Command | [CommandRequest](#steeleagle-protocol-services-remote_service-CommandRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) stream | Sends a service request to a vehicle core service (Control, Mission, etc.) over ZeroMQ and returns the response |
| CompileMission | [CompileMissionRequest](#steeleagle-protocol-services-remote_service-CompileMissionRequest) | [CompileMissionResponse](#steeleagle-protocol-services-remote_service-CompileMissionResponse) |  |





<a name="services_report_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/report_service.proto



<a name="steeleagle-protocol-services-report_service-ReportMessage"></a>

### ReportMessage
Message container for a report.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| report_code | [int32](#int32) |  | integer report code, interpreted by the backend |






<a name="steeleagle-protocol-services-report_service-SendReportRequest"></a>

### SendReportRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  | request data |
| report | [ReportMessage](#steeleagle-protocol-services-report_service-ReportMessage) |  | report data |












<a name="steeleagle-protocol-services-report_service-Report"></a>

### Report
Used to report messages to the Swarm Controller server.

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| SendReport | [SendReportRequest](#steeleagle-protocol-services-report_service-SendReportRequest) | [.steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) | Send a report to the server. |





<a name="testing_testing-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## testing/testing.proto



<a name="steeleagle-protocol-testing-ServiceReady"></a>

### ServiceReady



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| readied_service | [ServiceType](#steeleagle-protocol-testing-ServiceType) |  | Indicates which service is ready for testing |








<a name="steeleagle-protocol-testing-ServiceType"></a>

### ServiceType
Types of test messages for testing infrastructure

| Name | Number | Description |
| ---- | ------ | ----------- |
| CORE_SERVICES | 0 |  |
| STREAM_SERVICES | 1 |  |
| MISSION_SERVICE | 2 |  |
| DRIVER_CONTROL_SERVICE | 3 |  |










## Scalar Value Types

| .proto Type | Notes | C++ | Java | Python | Go | C# | PHP | Ruby |
| ----------- | ----- | --- | ---- | ------ | -- | -- | --- | ---- |
| <a name="double" /> double |  | double | double | float | float64 | double | float | Float |
| <a name="float" /> float |  | float | float | float | float32 | float | float | Float |
| <a name="int32" /> int32 | Uses variable-length encoding. Inefficient for encoding negative numbers – if your field is likely to have negative values, use sint32 instead. | int32 | int | int | int32 | int | integer | Bignum or Fixnum (as required) |
| <a name="int64" /> int64 | Uses variable-length encoding. Inefficient for encoding negative numbers – if your field is likely to have negative values, use sint64 instead. | int64 | long | int/long | int64 | long | integer/string | Bignum |
| <a name="uint32" /> uint32 | Uses variable-length encoding. | uint32 | int | int/long | uint32 | uint | integer | Bignum or Fixnum (as required) |
| <a name="uint64" /> uint64 | Uses variable-length encoding. | uint64 | long | int/long | uint64 | ulong | integer/string | Bignum or Fixnum (as required) |
| <a name="sint32" /> sint32 | Uses variable-length encoding. Signed int value. These more efficiently encode negative numbers than regular int32s. | int32 | int | int | int32 | int | integer | Bignum or Fixnum (as required) |
| <a name="sint64" /> sint64 | Uses variable-length encoding. Signed int value. These more efficiently encode negative numbers than regular int64s. | int64 | long | int/long | int64 | long | integer/string | Bignum |
| <a name="fixed32" /> fixed32 | Always four bytes. More efficient than uint32 if values are often greater than 2^28. | uint32 | int | int | uint32 | uint | integer | Bignum or Fixnum (as required) |
| <a name="fixed64" /> fixed64 | Always eight bytes. More efficient than uint64 if values are often greater than 2^56. | uint64 | long | int/long | uint64 | ulong | integer/string | Bignum |
| <a name="sfixed32" /> sfixed32 | Always four bytes. | int32 | int | int | int32 | int | integer | Bignum or Fixnum (as required) |
| <a name="sfixed64" /> sfixed64 | Always eight bytes. | int64 | long | int/long | int64 | long | integer/string | Bignum |
| <a name="bool" /> bool |  | bool | boolean | boolean | bool | bool | boolean | TrueClass/FalseClass |
| <a name="string" /> string | A string must always contain UTF-8 encoded or 7-bit ASCII text. | string | String | str/unicode | string | string | string | String (UTF-8) |
| <a name="bytes" /> bytes | May contain any arbitrary sequence of bytes. | string | ByteString | str | []byte | ByteString | string | String (ASCII-8BIT) |
