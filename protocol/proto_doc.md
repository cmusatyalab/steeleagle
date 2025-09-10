# Protocol Documentation
<a name="top"></a>

## Table of Contents

- [common.proto](#common-proto)
    - [Location](#steeleagle-protocol-common-Location)
    - [Pose](#steeleagle-protocol-common-Pose)
    - [Position](#steeleagle-protocol-common-Position)
    - [Request](#steeleagle-protocol-common-Request)
    - [Response](#steeleagle-protocol-common-Response)
    - [Velocity](#steeleagle-protocol-common-Velocity)
  
    - [ResponseStatus](#steeleagle-protocol-common-ResponseStatus)
  
- [messages/compute_payload.proto](#messages_compute_payload-proto)
    - [ComputePayload](#steeleagle-protocol-messages-compute_payload-ComputePayload)
  
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
    - [ConfigureDatasinksRequest](#steeleagle-protocol-services-compute_service-ConfigureDatasinksRequest)
    - [ConfigureDatasinksResponse](#steeleagle-protocol-services-compute_service-ConfigureDatasinksResponse)
    - [Datasink](#steeleagle-protocol-services-compute_service-Datasink)
    - [GetAvailableDatasinksRequest](#steeleagle-protocol-services-compute_service-GetAvailableDatasinksRequest)
    - [GetAvailableDatasinksResponse](#steeleagle-protocol-services-compute_service-GetAvailableDatasinksResponse)
  
    - [Compute](#steeleagle-protocol-services-compute_service-Compute)
  
- [services/control_service.proto](#services_control_service-proto)
    - [ArmRequest](#steeleagle-protocol-services-control_service-ArmRequest)
    - [ArmResponse](#steeleagle-protocol-services-control_service-ArmResponse)
    - [ConfigureImagingSensorStreamRequest](#steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamRequest)
    - [ConfigureImagingSensorStreamResponse](#steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamResponse)
    - [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-control_service-ConfigureTelemetryStreamRequest)
    - [ConfigureTelemetryStreamResponse](#steeleagle-protocol-services-control_service-ConfigureTelemetryStreamResponse)
    - [ConnectRequest](#steeleagle-protocol-services-control_service-ConnectRequest)
    - [ConnectResponse](#steeleagle-protocol-services-control_service-ConnectResponse)
    - [DisarmRequest](#steeleagle-protocol-services-control_service-DisarmRequest)
    - [DisarmResponse](#steeleagle-protocol-services-control_service-DisarmResponse)
    - [DisconnectRequest](#steeleagle-protocol-services-control_service-DisconnectRequest)
    - [DisconnectResponse](#steeleagle-protocol-services-control_service-DisconnectResponse)
    - [HoldRequest](#steeleagle-protocol-services-control_service-HoldRequest)
    - [HoldResponse](#steeleagle-protocol-services-control_service-HoldResponse)
    - [ImagingSensorConfiguration](#steeleagle-protocol-services-control_service-ImagingSensorConfiguration)
    - [IsConnectedRequest](#steeleagle-protocol-services-control_service-IsConnectedRequest)
    - [IsConnectedResponse](#steeleagle-protocol-services-control_service-IsConnectedResponse)
    - [KillRequest](#steeleagle-protocol-services-control_service-KillRequest)
    - [KillResponse](#steeleagle-protocol-services-control_service-KillResponse)
    - [LandRequest](#steeleagle-protocol-services-control_service-LandRequest)
    - [LandResponse](#steeleagle-protocol-services-control_service-LandResponse)
    - [ReturnToHomeRequest](#steeleagle-protocol-services-control_service-ReturnToHomeRequest)
    - [ReturnToHomeResponse](#steeleagle-protocol-services-control_service-ReturnToHomeResponse)
    - [SetGimbalPoseRequest](#steeleagle-protocol-services-control_service-SetGimbalPoseRequest)
    - [SetGimbalPoseResponse](#steeleagle-protocol-services-control_service-SetGimbalPoseResponse)
    - [SetGlobalPositionRequest](#steeleagle-protocol-services-control_service-SetGlobalPositionRequest)
    - [SetGlobalPositionResponse](#steeleagle-protocol-services-control_service-SetGlobalPositionResponse)
    - [SetHeadingRequest](#steeleagle-protocol-services-control_service-SetHeadingRequest)
    - [SetHeadingResponse](#steeleagle-protocol-services-control_service-SetHeadingResponse)
    - [SetHomeRequest](#steeleagle-protocol-services-control_service-SetHomeRequest)
    - [SetHomeResponse](#steeleagle-protocol-services-control_service-SetHomeResponse)
    - [SetRelativePositionRequest](#steeleagle-protocol-services-control_service-SetRelativePositionRequest)
    - [SetRelativePositionResponse](#steeleagle-protocol-services-control_service-SetRelativePositionResponse)
    - [SetVelocityRequest](#steeleagle-protocol-services-control_service-SetVelocityRequest)
    - [SetVelocityResponse](#steeleagle-protocol-services-control_service-SetVelocityResponse)
    - [TakeOffRequest](#steeleagle-protocol-services-control_service-TakeOffRequest)
    - [TakeOffResponse](#steeleagle-protocol-services-control_service-TakeOffResponse)
  
    - [AltitudeMode](#steeleagle-protocol-services-control_service-AltitudeMode)
    - [HeadingMode](#steeleagle-protocol-services-control_service-HeadingMode)
    - [PoseMode](#steeleagle-protocol-services-control_service-PoseMode)
    - [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame)
  
    - [Control](#steeleagle-protocol-services-control_service-Control)
  
- [services/flight_log_service.proto](#services_flight_log_service-proto)
    - [LogMessage](#steeleagle-protocol-services-flight_log_service-LogMessage)
    - [LogProtoRequest](#steeleagle-protocol-services-flight_log_service-LogProtoRequest)
    - [LogProtoResponse](#steeleagle-protocol-services-flight_log_service-LogProtoResponse)
    - [LogRequest](#steeleagle-protocol-services-flight_log_service-LogRequest)
    - [LogResponse](#steeleagle-protocol-services-flight_log_service-LogResponse)
    - [ReqRepProto](#steeleagle-protocol-services-flight_log_service-ReqRepProto)
  
    - [LogType](#steeleagle-protocol-services-flight_log_service-LogType)
  
    - [FlightLog](#steeleagle-protocol-services-flight_log_service-FlightLog)
  
- [services/mission_service.proto](#services_mission_service-proto)
    - [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamRequest)
    - [ConfigureTelemetryStreamResponse](#steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamResponse)
    - [MissionData](#steeleagle-protocol-services-mission_service-MissionData)
    - [NotifyRequest](#steeleagle-protocol-services-mission_service-NotifyRequest)
    - [NotifyResponse](#steeleagle-protocol-services-mission_service-NotifyResponse)
    - [StartRequest](#steeleagle-protocol-services-mission_service-StartRequest)
    - [StartResponse](#steeleagle-protocol-services-mission_service-StartResponse)
    - [StopRequest](#steeleagle-protocol-services-mission_service-StopRequest)
    - [StopResponse](#steeleagle-protocol-services-mission_service-StopResponse)
    - [UploadRequest](#steeleagle-protocol-services-mission_service-UploadRequest)
    - [UploadResponse](#steeleagle-protocol-services-mission_service-UploadResponse)
  
    - [Mission](#steeleagle-protocol-services-mission_service-Mission)
  
- [services/remote_service.proto](#services_remote_service-proto)
    - [RemoteControlRequest](#steeleagle-protocol-services-remote_service-RemoteControlRequest)
    - [RemoteControlResponse](#steeleagle-protocol-services-remote_service-RemoteControlResponse)
  
    - [Remote](#steeleagle-protocol-services-remote_service-Remote)
  
- [services/report_service.proto](#services_report_service-proto)
    - [ReportMessage](#steeleagle-protocol-services-report_service-ReportMessage)
    - [SendReportRequest](#steeleagle-protocol-services-report_service-SendReportRequest)
    - [SendReportResponse](#steeleagle-protocol-services-report_service-SendReportResponse)
  
    - [Report](#steeleagle-protocol-services-report_service-Report)
  
- [testing/testing.proto](#testing_testing-proto)
    - [ServiceReady](#steeleagle-protocol-testing-ServiceReady)
  
    - [ServiceType](#steeleagle-protocol-testing-ServiceType)
  
- [Scalar Value Types](#scalar-value-types)



<a name="common-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## common.proto



<a name="steeleagle-protocol-common-Location"></a>

### Location
Location in global coordinates [latitude, longitude]


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| latitude | [double](#double) |  |  |
| longitude | [double](#double) |  |  |
| altitude | [double](#double) |  | Above MSL [meters] |
| heading | [double](#double) |  |  |






<a name="steeleagle-protocol-common-Pose"></a>

### Pose
Angular offsets or poses in 3 dimensions [degrees]


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| pitch | [double](#double) |  |  |
| roll | [double](#double) |  |  |
| yaw | [double](#double) |  |  |






<a name="steeleagle-protocol-common-Position"></a>

### Position
Position offset relative to home or current location [meters]


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| x | [double](#double) |  | Forward/north offset |
| y | [double](#double) |  | Right/east offset |
| z | [double](#double) |  | Up offset |
| angle | [double](#double) |  | Angular offset [degrees] |






<a name="steeleagle-protocol-common-Request"></a>

### Request
Request object for additional request info


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  |  |






<a name="steeleagle-protocol-common-Response"></a>

### Response



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| status | [ResponseStatus](#steeleagle-protocol-common-ResponseStatus) |  |  |
| response_string | [string](#string) |  | Detailed message on reason for response |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  |  |






<a name="steeleagle-protocol-common-Velocity"></a>

### Velocity
Representation of the speed in 3-dimensions [meters/s]


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| x_vel | [double](#double) |  | Forward/north velocity |
| y_vel | [double](#double) |  | Right/east velocity |
| z_vel | [double](#double) |  | Up velocity |
| angular_vel | [double](#double) |  | Angular velocity [degrees/s] |





 


<a name="steeleagle-protocol-common-ResponseStatus"></a>

### ResponseStatus
Responses for RPC functions

| Name | Number | Description |
| ---- | ------ | ----------- |
| OK | 0 | Command received |
| IN_PROGRESS | 1 | Command in progress |
| COMPLETED | 2 | Command finished without error |
| CANCELLED | 3 | The following are gRPC base status codes, more info can be found at: https://grpc.github.io/grpc/core/md_doc_statuscodes.html To translate a gRPC error code to a SteelEagle response code, add 2 to its enum value |
| UNKNOWN | 4 |  |
| INVALID_ARGUMENT | 5 |  |
| DEADLINE_EXCEEDED | 6 |  |
| NOT_FOUND | 7 |  |
| ALREADY_EXISTS | 8 |  |
| PERMISSION_DENIED | 9 |  |
| RESOURCE_EXHAUSTED | 10 |  |
| FAILED_PRECONDITION | 11 |  |
| ABORTED | 12 |  |
| OUT_OF_RANGE | 13 |  |
| UNIMPLEMENTED | 14 |  |
| INTERNAL | 15 |  |
| UNAVAILABLE | 16 |  |
| DATA_LOSS | 17 |  |
| UNAUTHENTICATED | 18 |  |


 

 

 



<a name="messages_compute_payload-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## messages/compute_payload.proto



<a name="steeleagle-protocol-messages-compute_payload-ComputePayload"></a>

### ComputePayload
Messages/calls related to the computation component of SteelEagle.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| registering | [bool](#bool) |  | Designates an initial request to register a vehicle |
| vehicle_telem | [steeleagle.protocol.messages.telemetry.DriverTelemetry](#steeleagle-protocol-messages-telemetry-DriverTelemetry) |  | The driver telemetry data for the vehicle |
| mission_telem | [steeleagle.protocol.messages.telemetry.MissionTelemetry](#steeleagle-protocol-messages-telemetry-MissionTelemetry) |  | The mission telemetry data for the vehicle |





 

 

 

 



<a name="messages_result-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## messages/result.proto



<a name="steeleagle-protocol-messages-result-AvoidanceResult"></a>

### AvoidanceResult



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| actuation_vector | [double](#double) |  | Actuation vector towards safe area |






<a name="steeleagle-protocol-messages-result-BoundingBox"></a>

### BoundingBox
Defines the upper left and lower right corners of a detected object
in an image frame. Origin (0,0) is the top left corner of the input image.
(image_height, image_width) is the bottom right corner.
Also the class and confidence threshold associated with the box.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| y_min | [double](#double) |  | wrt to image size |
| x_min | [double](#double) |  | wrt to image size |
| y_max | [double](#double) |  | wrt to image size |
| x_max | [double](#double) |  | wrt to image size |
| class_name | [string](#string) |  |  |
| confidence | [float](#float) |  |  |






<a name="steeleagle-protocol-messages-result-ComputeResult"></a>

### ComputeResult



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | Inference timestamp |
| engine_name | [string](#string) |  |  |
| detection_result | [DetectionResult](#steeleagle-protocol-messages-result-DetectionResult) |  |  |
| avoidance_result | [AvoidanceResult](#steeleagle-protocol-messages-result-AvoidanceResult) |  |  |
| slam_result | [SLAMResult](#steeleagle-protocol-messages-result-SLAMResult) |  |  |
| generic_result | [string](#string) |  | JSON result |






<a name="steeleagle-protocol-messages-result-Detection"></a>

### Detection



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| detection_id | [uint64](#uint64) |  | Can be multiple objects per frame |
| class_name | [string](#string) |  |  |
| score | [double](#double) |  |  |
| bbox | [BoundingBox](#steeleagle-protocol-messages-result-BoundingBox) |  |  |
| hsv_filter_passed | [bool](#bool) |  |  |






<a name="steeleagle-protocol-messages-result-DetectionResult"></a>

### DetectionResult



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| detections | [Detection](#steeleagle-protocol-messages-result-Detection) | repeated |  |






<a name="steeleagle-protocol-messages-result-FrameResult"></a>

### FrameResult
Compute results generated by datasink modules


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| type | [string](#string) |  |  |
| frame_id | [uint64](#uint64) |  | For correlation |
| result | [ComputeResult](#steeleagle-protocol-messages-result-ComputeResult) | repeated |  |






<a name="steeleagle-protocol-messages-result-HSV"></a>

### HSV
Color filter represented by hue, saturation, and value
Uses OpenCV ranges: https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| h | [uint32](#uint32) |  | hue range is [0,179] |
| s | [uint32](#uint32) |  | saturation range is [0,255] |
| v | [uint32](#uint32) |  | value range is [0,255] |






<a name="steeleagle-protocol-messages-result-SLAMResult"></a>

### SLAMResult



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| relative_position | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  |  |
| global_position | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  |  |





 

 

 

 



<a name="messages_telemetry-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## messages/telemetry.proto



<a name="steeleagle-protocol-messages-telemetry-AlertInfo"></a>

### AlertInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| battery_warning | [BatteryWarning](#steeleagle-protocol-messages-telemetry-BatteryWarning) |  | Battery warnings |
| gps_warning | [GPSWarning](#steeleagle-protocol-messages-telemetry-GPSWarning) |  | GPS warnings |
| magnetometer_warning | [MagnetometerWarning](#steeleagle-protocol-messages-telemetry-MagnetometerWarning) |  | Magnetometer warnings |
| connection_warning | [ConnectionWarning](#steeleagle-protocol-messages-telemetry-ConnectionWarning) |  | Connection warnings |
| compass_warning | [CompassWarning](#steeleagle-protocol-messages-telemetry-CompassWarning) |  | Compass warnings |






<a name="steeleagle-protocol-messages-telemetry-BatteryInfo"></a>

### BatteryInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| percentage | [uint32](#uint32) |  | Battery level [0-100]% |






<a name="steeleagle-protocol-messages-telemetry-CommsInfo"></a>

### CommsInfo







<a name="steeleagle-protocol-messages-telemetry-DriverTelemetry"></a>

### DriverTelemetry
Telemetry message for the vehicle, originated from the driver module


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | Timestamp of message |
| telemetry_stream_info | [TelemetryStreamInfo](#steeleagle-protocol-messages-telemetry-TelemetryStreamInfo) |  | Info about current telemetry stream |
| vehicle_info | [VehicleInfo](#steeleagle-protocol-messages-telemetry-VehicleInfo) |  | The vehicle that this telemetry corresponds to |
| position_info | [PositionInfo](#steeleagle-protocol-messages-telemetry-PositionInfo) |  | Positional info about the vehicle |
| gimbal_info | [GimbalInfo](#steeleagle-protocol-messages-telemetry-GimbalInfo) |  | Status on attached gimbals and their orientations |
| imaging_sensor_info | [ImagingSensorInfo](#steeleagle-protocol-messages-telemetry-ImagingSensorInfo) |  | Information about the vehicle imaging sensors |
| alert_info | [AlertInfo](#steeleagle-protocol-messages-telemetry-AlertInfo) |  | Enumeration of vehicle warnings |






<a name="steeleagle-protocol-messages-telemetry-Frame"></a>

### Frame
Imaging sensor frame data streamed from the driver module


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | Capture timestamp of the frame |
| data | [bytes](#bytes) |  | Raw bytes representing the frame |
| h_res | [uint64](#uint64) |  | Horizontal frame resolution in pixels |
| v_res | [uint64](#uint64) |  | Vertical frame resolution in pixels |
| d_res | [uint64](#uint64) |  | Depth resolution in pixels |
| channels | [uint64](#uint64) |  | Number of channels |
| id | [uint64](#uint64) |  | Frame ID for future correlation |






<a name="steeleagle-protocol-messages-telemetry-GPSInfo"></a>

### GPSInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| satellites | [uint32](#uint32) |  | Number of satellites used in GPS fix |






<a name="steeleagle-protocol-messages-telemetry-GimbalInfo"></a>

### GimbalInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| num_gimbals | [uint32](#uint32) |  | Number of connected gimbals |
| gimbals | [GimbalStatus](#steeleagle-protocol-messages-telemetry-GimbalStatus) | repeated | List of connected gimbals |






<a name="steeleagle-protocol-messages-telemetry-GimbalStatus"></a>

### GimbalStatus



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| id | [uint32](#uint32) |  | ID of the gimbal |
| pose_body | [steeleagle.protocol.common.Pose](#steeleagle-protocol-common-Pose) |  | Current pose in the body reference frame |
| pose_enu | [steeleagle.protocol.common.Pose](#steeleagle-protocol-common-Pose) |  | Current pose in the ENU reference frame |






<a name="steeleagle-protocol-messages-telemetry-ImagingSensorInfo"></a>

### ImagingSensorInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| stream_status | [ImagingSensorStreamStatus](#steeleagle-protocol-messages-telemetry-ImagingSensorStreamStatus) |  | Status of current imaging sensor streams |
| sensors | [ImagingSensorStatus](#steeleagle-protocol-messages-telemetry-ImagingSensorStatus) | repeated | List of connected imaging sensors |






<a name="steeleagle-protocol-messages-telemetry-ImagingSensorStatus"></a>

### ImagingSensorStatus



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| id | [uint32](#uint32) |  | ID of the imaging sensor |
| type | [ImagingSensorType](#steeleagle-protocol-messages-telemetry-ImagingSensorType) |  | Type of the imaging sensor |
| active | [bool](#bool) |  | Indicates whether the imaging sensor is currently streaming |
| supports_secondary | [bool](#bool) |  | Indicates whether the imaging sensor supports background streaming |
| current_fps | [uint32](#uint32) |  | Current streaming frames per second |
| max_fps | [uint32](#uint32) |  | Maximum streaming frames per second |
| h_res | [uint32](#uint32) |  | Horizontal resolution |
| v_res | [uint32](#uint32) |  | Vertical resolution |
| channels | [uint32](#uint32) |  | Number of image channels |
| h_fov | [uint32](#uint32) |  | Horizontal FOV |
| v_fov | [uint32](#uint32) |  | Vertical FOV |
| gimbal_mounted | [bool](#bool) |  | Indicates if imaging sensor is gimbal mounted |
| gimbal_id | [uint32](#uint32) |  | Indicates which gimbal the imaging sensor is mounted on |






<a name="steeleagle-protocol-messages-telemetry-ImagingSensorStreamStatus"></a>

### ImagingSensorStreamStatus



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| stream_capacity | [uint32](#uint32) |  | The total number of allowed simultaneously streaming cameras |
| num_streams | [uint32](#uint32) |  | The total number of currently streaming cameras |
| primary_cam | [uint32](#uint32) |  | ID of the primary camera |
| secondary_cams | [uint32](#uint32) | repeated | IDs of the secondary active cameras |






<a name="steeleagle-protocol-messages-telemetry-MissionInfo"></a>

### MissionInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| name | [string](#string) |  | Mission name |
| hash | [int64](#int64) |  | Mission hash to establish version uniqueness |
| age | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | Timestamp of upload |
| exec_state | [MissionExecState](#steeleagle-protocol-messages-telemetry-MissionExecState) |  | Execution state of the mission |
| task_state | [string](#string) |  | Task state of the mission (plaintext), if active |






<a name="steeleagle-protocol-messages-telemetry-MissionTelemetry"></a>

### MissionTelemetry
Telemetry message for the mission, originated from the mission module


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | Timestamp of message |
| telemetry_stream_info | [TelemetryStreamInfo](#steeleagle-protocol-messages-telemetry-TelemetryStreamInfo) |  | Info about the current telemetry stream |
| mission_info | [MissionInfo](#steeleagle-protocol-messages-telemetry-MissionInfo) | repeated | Info about the current mission states |






<a name="steeleagle-protocol-messages-telemetry-PositionInfo"></a>

### PositionInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| home | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | Global position that will be used when returning home |
| global_position | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | Current global position of the vehicle |
| relative_position | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | Current local position of the vehicle in the global ENU (East, North, Up) coordinate frame, relative to take off position |
| velocity_enu | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | Current velocity of the vehicle in the global ENU (East, North, Up) coordinate frame |
| velocity_body | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | Current velocity of the vehicle in the body (forward, right, up) coordinate frame |
| setpoint_info | [SetpointInfo](#steeleagle-protocol-messages-telemetry-SetpointInfo) |  | Info on the current vehicle setpoint |






<a name="steeleagle-protocol-messages-telemetry-SetpointInfo"></a>

### SetpointInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| position_body_sp | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | Default to all zeros local position setpoint |
| position_enu_sp | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  |  |
| global_sp | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  |  |
| velocity_body_sp | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  |  |
| velocity_enu_sp | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  |  |






<a name="steeleagle-protocol-messages-telemetry-TelemetryStreamInfo"></a>

### TelemetryStreamInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| current_frequency | [uint32](#uint32) |  | Current frequency of telemetry messages, in Hz |
| max_frequency | [uint32](#uint32) |  | Maximum frequency of telemetry messages, in Hz |
| uptime | [google.protobuf.Duration](#google-protobuf-Duration) |  | Uptime of the stream |






<a name="steeleagle-protocol-messages-telemetry-VehicleInfo"></a>

### VehicleInfo



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| name | [string](#string) |  | The vehicle that this telemetry corresponds to |
| model | [string](#string) |  | Model of the vehicle |
| manufacturer | [string](#string) |  | Manufacturer of the vehicle |
| motion_status | [MotionStatus](#steeleagle-protocol-messages-telemetry-MotionStatus) |  | Current status of the vehicle |
| battery_info | [BatteryInfo](#steeleagle-protocol-messages-telemetry-BatteryInfo) |  | Battery info for the vehicle |
| gps_info | [GPSInfo](#steeleagle-protocol-messages-telemetry-GPSInfo) |  | GPS sensor info for the vehicle |
| comms_info | [CommsInfo](#steeleagle-protocol-messages-telemetry-CommsInfo) |  | Communications info for the vehicle |





 


<a name="steeleagle-protocol-messages-telemetry-BatteryWarning"></a>

### BatteryWarning


| Name | Number | Description |
| ---- | ------ | ----------- |
| NONE | 0 | The vehicle is above 30% battery |
| LOW | 1 | The vehicle is below 30% battery |
| CRITICAL | 2 | The vehicle is below 15% battery |



<a name="steeleagle-protocol-messages-telemetry-CompassWarning"></a>

### CompassWarning


| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_COMPASS_WARNING | 0 | Absolute heading is nominal |
| WEAK_HEADING_LOCK | 1 | Absolute heading is available but may be incorrect |
| NO_HEADING_LOCK | 2 | No absolute heading available from the vehicle |



<a name="steeleagle-protocol-messages-telemetry-ConnectionWarning"></a>

### ConnectionWarning


| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_CONNECTION_WARNING | 0 | Connection to remote server is nominal |
| DISCONNECTED | 1 | Contact has been lost with the remote server |
| WEAK_CONNECTION | 2 | Connection is experiencing interference or is weak |



<a name="steeleagle-protocol-messages-telemetry-GPSWarning"></a>

### GPSWarning


| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_GPS_WARNING | 0 | GPS readings are nominal and a fix has been achieved |
| WEAK_SIGNAL | 1 | Weak GPS fix, expect errant global position data |
| NO_FIX | 2 | No GPS fix |



<a name="steeleagle-protocol-messages-telemetry-ImagingSensorType"></a>

### ImagingSensorType
Data related to imaging sensors

| Name | Number | Description |
| ---- | ------ | ----------- |
| UNKNOWN_IMAGING_SENSOR_TYPE | 0 |  |
| RGB | 1 |  |
| STEREO | 2 |  |
| THERMAL | 3 |  |
| NIGHT | 4 |  |
| LIDAR | 5 |  |
| RGBD | 6 |  |
| TOF | 7 |  |
| RADAR | 8 |  |



<a name="steeleagle-protocol-messages-telemetry-MagnetometerWarning"></a>

### MagnetometerWarning


| Name | Number | Description |
| ---- | ------ | ----------- |
| NO_MAGNETOMETER_WARNING | 0 | Magnetometer readings are nominal |
| PERTURBATION | 1 | The vehicle is experiencing magnetic perturbations |



<a name="steeleagle-protocol-messages-telemetry-MissionExecState"></a>

### MissionExecState
Data related to the current mission

| Name | Number | Description |
| ---- | ------ | ----------- |
| READY | 0 | Mission is ready to be executed |
| IN_PROGRESS | 1 | Mission is in progress |
| PAUSED | 3 | Mission is paused |
| COMPLETED | 4 | Mission has been completed |
| CANCELED | 5 | Mission was cancelled |



<a name="steeleagle-protocol-messages-telemetry-MotionStatus"></a>

### MotionStatus


| Name | Number | Description |
| ---- | ------ | ----------- |
| MOTORS_OFF | 0 |  |
| RAMPING | 1 |  |
| IDLE | 2 |  |
| IN_TRANSIT | 3 |  |


 

 

 



<a name="services_compute_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/compute_service.proto



<a name="steeleagle-protocol-services-compute_service-ConfigureDatasinksRequest"></a>

### ConfigureDatasinksRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| name | [string](#string) | repeated | Name of target datasinks |
| activate | [bool](#bool) | repeated | Switch to activate/deactivate datasinks |






<a name="steeleagle-protocol-services-compute_service-ConfigureDatasinksResponse"></a>

### ConfigureDatasinksResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-compute_service-Datasink"></a>

### Datasink



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| name | [string](#string) |  | Name of the datasink |
| topic | [string](#string) |  | Publishing topic on the datastore |
| model | [string](#string) |  | Type of model used |
| active | [bool](#bool) |  | Indicates if the datasink is active |
| uptime | [google.protobuf.Duration](#google-protobuf-Duration) |  | Uptime duration |






<a name="steeleagle-protocol-services-compute_service-GetAvailableDatasinksRequest"></a>

### GetAvailableDatasinksRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-compute_service-GetAvailableDatasinksResponse"></a>

### GetAvailableDatasinksResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |
| datasinks | [Datasink](#steeleagle-protocol-services-compute_service-Datasink) | repeated | List of available datasinks |





 

 

 


<a name="steeleagle-protocol-services-compute_service-Compute"></a>

### Compute
Used to configure datasinks for sensor streams

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| GetAvailableDatasinks | [GetAvailableDatasinksRequest](#steeleagle-protocol-services-compute_service-GetAvailableDatasinksRequest) | [GetAvailableDatasinksResponse](#steeleagle-protocol-services-compute_service-GetAvailableDatasinksResponse) | Get all available compute engines, both local and remote |
| ConfigureDatasinks | [ConfigureDatasinksRequest](#steeleagle-protocol-services-compute_service-ConfigureDatasinksRequest) | [ConfigureDatasinksResponse](#steeleagle-protocol-services-compute_service-ConfigureDatasinksResponse) | Configure compute preferences |

 



<a name="services_control_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/control_service.proto



<a name="steeleagle-protocol-services-control_service-ArmRequest"></a>

### ArmRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-ArmResponse"></a>

### ArmResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamRequest"></a>

### ConfigureImagingSensorStreamRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| configurations | [ImagingSensorConfiguration](#steeleagle-protocol-services-control_service-ImagingSensorConfiguration) | repeated | List of configurations to be updated |






<a name="steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamResponse"></a>

### ConfigureImagingSensorStreamResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-ConfigureTelemetryStreamRequest"></a>

### ConfigureTelemetryStreamRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| frequency | [uint32](#uint32) |  | Target frequency of telemetry generation, in Hz |






<a name="steeleagle-protocol-services-control_service-ConfigureTelemetryStreamResponse"></a>

### ConfigureTelemetryStreamResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-ConnectRequest"></a>

### ConnectRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-ConnectResponse"></a>

### ConnectResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-DisarmRequest"></a>

### DisarmRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-DisarmResponse"></a>

### DisarmResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-DisconnectRequest"></a>

### DisconnectRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-DisconnectResponse"></a>

### DisconnectResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-HoldRequest"></a>

### HoldRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-HoldResponse"></a>

### HoldResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-ImagingSensorConfiguration"></a>

### ImagingSensorConfiguration



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| id | [uint32](#uint32) |  | Target imaging sensor ID |
| set_primary | [bool](#bool) |  | Set this sensor as the primary stream |
| set_fps | [uint32](#uint32) |  | Target FPS for stream |






<a name="steeleagle-protocol-services-control_service-IsConnectedRequest"></a>

### IsConnectedRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-IsConnectedResponse"></a>

### IsConnectedResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |
| is_connected | [bool](#bool) |  |  |






<a name="steeleagle-protocol-services-control_service-KillRequest"></a>

### KillRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-KillResponse"></a>

### KillResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-LandRequest"></a>

### LandRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-LandResponse"></a>

### LandResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-ReturnToHomeRequest"></a>

### ReturnToHomeRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-control_service-ReturnToHomeResponse"></a>

### ReturnToHomeResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-SetGimbalPoseRequest"></a>

### SetGimbalPoseRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| gimbal_id | [uint32](#uint32) |  | ID of the target gimbal |
| pose | [steeleagle.protocol.common.Pose](#steeleagle-protocol-common-Pose) |  | Target pose |
| mode | [PoseMode](#steeleagle-protocol-services-control_service-PoseMode) | optional | Specifies how to interpret the target pose |






<a name="steeleagle-protocol-services-control_service-SetGimbalPoseResponse"></a>

### SetGimbalPoseResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-SetGlobalPositionRequest"></a>

### SetGlobalPositionRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| location | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | Target location |
| altitude_mode | [AltitudeMode](#steeleagle-protocol-services-control_service-AltitudeMode) | optional | Determines whether the drone will consider altitude as meters above MSL (Mean Sea Level), or relative to its takeoff location (default ABSOLUTE) |
| heading_mode | [HeadingMode](#steeleagle-protocol-services-control_service-HeadingMode) | optional | Determines how the drone will orient during transit (default TO_TARGET) |
| max_velocity | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) | optional | Maximum velocity during transit, north_vel determines horizontal velocity, up_vel determines vertical velocity, and angular_vel determines angular velocity (default 5 m/s) |






<a name="steeleagle-protocol-services-control_service-SetGlobalPositionResponse"></a>

### SetGlobalPositionResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-SetHeadingRequest"></a>

### SetHeadingRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| location | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | Target heading or global location to look at |
| heading_mode | [HeadingMode](#steeleagle-protocol-services-control_service-HeadingMode) | optional | Determines how the drone will orient |






<a name="steeleagle-protocol-services-control_service-SetHeadingResponse"></a>

### SetHeadingResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-SetHomeRequest"></a>

### SetHomeRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| location | [steeleagle.protocol.common.Location](#steeleagle-protocol-common-Location) |  | New home location |






<a name="steeleagle-protocol-services-control_service-SetHomeResponse"></a>

### SetHomeResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-SetRelativePositionRequest"></a>

### SetRelativePositionRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| position | [steeleagle.protocol.common.Position](#steeleagle-protocol-common-Position) |  | Target position |
| max_velocity | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) | optional | Maximum velocity during transit, x_vel determines horizontal velocity, up_vel determines vertical velocity, and angular_vel determines angular velocity |
| frame | [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame) | optional | Frame of reference |






<a name="steeleagle-protocol-services-control_service-SetRelativePositionResponse"></a>

### SetRelativePositionResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-SetVelocityRequest"></a>

### SetVelocityRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| velocity | [steeleagle.protocol.common.Velocity](#steeleagle-protocol-common-Velocity) |  | Target velocity |
| frame | [ReferenceFrame](#steeleagle-protocol-services-control_service-ReferenceFrame) | optional | Frame of reference |






<a name="steeleagle-protocol-services-control_service-SetVelocityResponse"></a>

### SetVelocityResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-control_service-TakeOffRequest"></a>

### TakeOffRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| take_off_altitude | [float](#float) |  | Take off height in relative altitude [meters] |






<a name="steeleagle-protocol-services-control_service-TakeOffResponse"></a>

### TakeOffResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |





 


<a name="steeleagle-protocol-services-control_service-AltitudeMode"></a>

### AltitudeMode


| Name | Number | Description |
| ---- | ------ | ----------- |
| ABSOLUTE | 0 | Meters above Mean Sea Level |
| RELATIVE | 1 | Meters above takeoff location |



<a name="steeleagle-protocol-services-control_service-HeadingMode"></a>

### HeadingMode


| Name | Number | Description |
| ---- | ------ | ----------- |
| TO_TARGET | 0 | Orient towards the target location |
| HEADING_START | 1 | Orient towards the given heading |



<a name="steeleagle-protocol-services-control_service-PoseMode"></a>

### PoseMode


| Name | Number | Description |
| ---- | ------ | ----------- |
| ANGLE | 0 | Absolute angle |
| OFFSET | 1 | Offset from current |
| VELOCITY | 2 | Rotational velocities |



<a name="steeleagle-protocol-services-control_service-ReferenceFrame"></a>

### ReferenceFrame


| Name | Number | Description |
| ---- | ------ | ----------- |
| BODY | 0 | Vehicle reference frame |
| ENU | 1 | Global (East, North, Up) reference frame |


 

 


<a name="steeleagle-protocol-services-control_service-Control"></a>

### Control
Used for low-level control of a vehicle

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| Connect | [ConnectRequest](#steeleagle-protocol-services-control_service-ConnectRequest) | [ConnectResponse](#steeleagle-protocol-services-control_service-ConnectResponse) | Connects to the vehicle |
| IsConnected | [IsConnectedRequest](#steeleagle-protocol-services-control_service-IsConnectedRequest) | [IsConnectedResponse](#steeleagle-protocol-services-control_service-IsConnectedResponse) | Checks whether the vehicle is successfully connected |
| Disconnect | [DisconnectRequest](#steeleagle-protocol-services-control_service-DisconnectRequest) | [DisconnectResponse](#steeleagle-protocol-services-control_service-DisconnectResponse) | Disconnects from the vehicle |
| Arm | [ArmRequest](#steeleagle-protocol-services-control_service-ArmRequest) | [ArmResponse](#steeleagle-protocol-services-control_service-ArmResponse) | Order the vehicle to arm |
| Disarm | [DisarmRequest](#steeleagle-protocol-services-control_service-DisarmRequest) | [DisarmResponse](#steeleagle-protocol-services-control_service-DisarmResponse) | Order the vehicle to disarm |
| TakeOff | [TakeOffRequest](#steeleagle-protocol-services-control_service-TakeOffRequest) | [TakeOffResponse](#steeleagle-protocol-services-control_service-TakeOffResponse) stream | Order the vehicle to take off |
| Land | [LandRequest](#steeleagle-protocol-services-control_service-LandRequest) | [LandResponse](#steeleagle-protocol-services-control_service-LandResponse) stream | Land the vehicle at its current position |
| Hold | [HoldRequest](#steeleagle-protocol-services-control_service-HoldRequest) | [HoldResponse](#steeleagle-protocol-services-control_service-HoldResponse) stream | Order the vehicle to hold/loiter |
| Kill | [KillRequest](#steeleagle-protocol-services-control_service-KillRequest) | [KillResponse](#steeleagle-protocol-services-control_service-KillResponse) stream | Emergency shutdown of the vehicle motors |
| SetHome | [SetHomeRequest](#steeleagle-protocol-services-control_service-SetHomeRequest) | [SetHomeResponse](#steeleagle-protocol-services-control_service-SetHomeResponse) | Changes the home destination for the vehicle |
| ReturnToHome | [ReturnToHomeRequest](#steeleagle-protocol-services-control_service-ReturnToHomeRequest) | [ReturnToHomeResponse](#steeleagle-protocol-services-control_service-ReturnToHomeResponse) stream | Return to the vehicle home destination |
| SetGlobalPosition | [SetGlobalPositionRequest](#steeleagle-protocol-services-control_service-SetGlobalPositionRequest) | [SetGlobalPositionResponse](#steeleagle-protocol-services-control_service-SetGlobalPositionResponse) stream | Transit the vehicle to a target global position, expressed in global coordinates |
| SetRelativePosition | [SetRelativePositionRequest](#steeleagle-protocol-services-control_service-SetRelativePositionRequest) | [SetRelativePositionResponse](#steeleagle-protocol-services-control_service-SetRelativePositionResponse) stream | Transit the vehicle to a target position relative to the global ENU (East, North, Up) or vehicle frame of reference, in meters |
| SetVelocity | [SetVelocityRequest](#steeleagle-protocol-services-control_service-SetVelocityRequest) | [SetVelocityResponse](#steeleagle-protocol-services-control_service-SetVelocityResponse) stream | Transit the vehicle at a target velocity in the global ENU (East, North, Up) or vehicle frame of reference, in meters per second |
| SetHeading | [SetHeadingRequest](#steeleagle-protocol-services-control_service-SetHeadingRequest) | [SetHeadingResponse](#steeleagle-protocol-services-control_service-SetHeadingResponse) stream | Sets the heading of the vehicle |
| SetGimbalPose | [SetGimbalPoseRequest](#steeleagle-protocol-services-control_service-SetGimbalPoseRequest) | [SetGimbalPoseResponse](#steeleagle-protocol-services-control_service-SetGimbalPoseResponse) stream | Set the pose of the target gimbal |
| ConfigureImagingSensorStream | [ConfigureImagingSensorStreamRequest](#steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamRequest) | [ConfigureImagingSensorStreamResponse](#steeleagle-protocol-services-control_service-ConfigureImagingSensorStreamResponse) | Set the vehicle video stream parameters |
| ConfigureTelemetryStream | [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-control_service-ConfigureTelemetryStreamRequest) | [ConfigureTelemetryStreamResponse](#steeleagle-protocol-services-control_service-ConfigureTelemetryStreamResponse) | Set the vehicle telemetry stream parameters |

 



<a name="services_flight_log_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/flight_log_service.proto



<a name="steeleagle-protocol-services-flight_log_service-LogMessage"></a>

### LogMessage



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| type | [LogType](#steeleagle-protocol-services-flight_log_service-LogType) |  |  |
| msg | [string](#string) |  |  |






<a name="steeleagle-protocol-services-flight_log_service-LogProtoRequest"></a>

### LogProtoRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| topic | [string](#string) |  |  |
| reqrep_proto | [ReqRepProto](#steeleagle-protocol-services-flight_log_service-ReqRepProto) |  |  |






<a name="steeleagle-protocol-services-flight_log_service-LogProtoResponse"></a>

### LogProtoResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-flight_log_service-LogRequest"></a>

### LogRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| topic | [string](#string) |  |  |
| log | [LogMessage](#steeleagle-protocol-services-flight_log_service-LogMessage) |  |  |






<a name="steeleagle-protocol-services-flight_log_service-LogResponse"></a>

### LogResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-flight_log_service-ReqRepProto"></a>

### ReqRepProto



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |
| name | [string](#string) |  | Name of the request and associated service |
| content | [string](#string) |  | Plaintext representation of the proto contents |





 


<a name="steeleagle-protocol-services-flight_log_service-LogType"></a>

### LogType


| Name | Number | Description |
| ---- | ------ | ----------- |
| INFO | 0 |  |
| DEBUG | 1 |  |
| WARNING | 2 |  |
| ERROR | 3 |  |


 

 


<a name="steeleagle-protocol-services-flight_log_service-FlightLog"></a>

### FlightLog
Used to log to a flight log

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| Log | [LogRequest](#steeleagle-protocol-services-flight_log_service-LogRequest) | [LogResponse](#steeleagle-protocol-services-flight_log_service-LogResponse) | Basic log endpoint |
| LogProto | [LogProtoRequest](#steeleagle-protocol-services-flight_log_service-LogProtoRequest) | [LogProtoResponse](#steeleagle-protocol-services-flight_log_service-LogProtoResponse) | Log a request/response proto |

 



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
| uri | [string](#string) |  | URI, either local or remote, of a mission file |






<a name="steeleagle-protocol-services-mission_service-NotifyRequest"></a>

### NotifyRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| notify_code | [int32](#int32) |  | Integer notification code, generated by the backend |
| notify_data | [google.protobuf.Any](#google-protobuf-Any) | optional | Extra data about notification |






<a name="steeleagle-protocol-services-mission_service-NotifyResponse"></a>

### NotifyResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-mission_service-StartRequest"></a>

### StartRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-mission_service-StartResponse"></a>

### StartResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-mission_service-StopRequest"></a>

### StopRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |






<a name="steeleagle-protocol-services-mission_service-StopResponse"></a>

### StopResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |






<a name="steeleagle-protocol-services-mission_service-UploadRequest"></a>

### UploadRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| mission | [MissionData](#steeleagle-protocol-services-mission_service-MissionData) |  | Data of the target mission |






<a name="steeleagle-protocol-services-mission_service-UploadResponse"></a>

### UploadResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |





 

 

 


<a name="steeleagle-protocol-services-mission_service-Mission"></a>

### Mission
Used to start a new mission or stop an active mission

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| Upload | [UploadRequest](#steeleagle-protocol-services-mission_service-UploadRequest) | [UploadResponse](#steeleagle-protocol-services-mission_service-UploadResponse) | Upload a mission for execution |
| Start | [StartRequest](#steeleagle-protocol-services-mission_service-StartRequest) | [StartResponse](#steeleagle-protocol-services-mission_service-StartResponse) | Start an uploaded mission |
| Stop | [StopRequest](#steeleagle-protocol-services-mission_service-StopRequest) | [StopResponse](#steeleagle-protocol-services-mission_service-StopResponse) | Stop the current mission |
| Notify | [NotifyRequest](#steeleagle-protocol-services-mission_service-NotifyRequest) | [NotifyResponse](#steeleagle-protocol-services-mission_service-NotifyResponse) | Send a notification to the current mission |
| ConfigureTelemetryStream | [ConfigureTelemetryStreamRequest](#steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamRequest) | [ConfigureTelemetryStreamResponse](#steeleagle-protocol-services-mission_service-ConfigureTelemetryStreamResponse) | Set the mission telemetry stream parameters |

 



<a name="services_remote_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/remote_service.proto



<a name="steeleagle-protocol-services-remote_service-RemoteControlRequest"></a>

### RemoteControlRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| sequence_number | [uint32](#uint32) |  | Since command sequencing is not built-in to ZeroMQ, it must be done manually |
| control_request | [google.protobuf.Any](#google-protobuf-Any) |  | Contains request data for an RPC call |
| method_name | [string](#string) |  | Fully qualified method name |
| identity | [string](#string) |  | Identity of the sender |






<a name="steeleagle-protocol-services-remote_service-RemoteControlResponse"></a>

### RemoteControlResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| sequence_number | [uint32](#uint32) |  | Since command sequencing is not built-in to ZeroMQ, it must be done manually |
| control_response | [google.protobuf.Any](#google-protobuf-Any) |  | Contains response data for an RPC call |
| identity | [string](#string) |  | Identity of the original sender |





 

 

 


<a name="steeleagle-protocol-services-remote_service-Remote"></a>

### Remote
Used to control a vehicle remotely over ZeroMQ
Not implemented as a gRPC service!

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| RemoteControl | [RemoteControlRequest](#steeleagle-protocol-services-remote_service-RemoteControlRequest) | [RemoteControlResponse](#steeleagle-protocol-services-remote_service-RemoteControlResponse) | Sends a request to one of the core services (Control, Mission, etc.) |

 



<a name="services_report_service-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## services/report_service.proto



<a name="steeleagle-protocol-services-report_service-ReportMessage"></a>

### ReportMessage



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| report_code | [int32](#int32) |  | Integer report code, interpreted by the backend |
| report_data | [google.protobuf.Any](#google-protobuf-Any) | optional | Extra data about report |






<a name="steeleagle-protocol-services-report_service-SendReportRequest"></a>

### SendReportRequest



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| request | [steeleagle.protocol.common.Request](#steeleagle-protocol-common-Request) |  |  |
| report | [ReportMessage](#steeleagle-protocol-services-report_service-ReportMessage) |  |  |






<a name="steeleagle-protocol-services-report_service-SendReportResponse"></a>

### SendReportResponse



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| response | [steeleagle.protocol.common.Response](#steeleagle-protocol-common-Response) |  |  |





 

 

 


<a name="steeleagle-protocol-services-report_service-Report"></a>

### Report
Used to report messages to the Swarm Controller server
or to other collaborative vehicles

| Method Name | Request Type | Response Type | Description |
| ----------- | ------------ | ------------- | ------------|
| SendReport | [SendReportRequest](#steeleagle-protocol-services-report_service-SendReportRequest) | [SendReportResponse](#steeleagle-protocol-services-report_service-SendReportResponse) | Send a report to the server, or to an intended recipient |

 



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

