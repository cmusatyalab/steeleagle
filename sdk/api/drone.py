import json

import grpc
from state_store import StateStore
from ..protocol.services import control_service_pb2, control_service_pb2_grpc
from ..protocol.services import report_service_pb2, report_service_pb2_grpc
from ..protocol.common_pb2 import common
from google.protobuf.json_format import ParseDict
from native import run_unary, run_streaming


class Drone:
    
    def __init__(self,
                 state_store: StateStore,
                 channel):
        
        self.state_store = state_store
        stub_channel = grpc.aio.insecure_channel(channel)
        self.control = control_service_pb2_grpc.ControlStub(stub_channel)
        self.report = report_service_pb2_grpc.ReportStub(stub_channel)

    def get_drone_state():
        pass

    async def connect(self, **kwargs) -> common.Response:
        req = control_service_pb2.ConnectRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.Connect, req)
        
    async def disconnect(self, **kwargs) -> common.Response:
        req = control_service_pb2.DisconnectRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.Disconnect, req)
    
    async def arm(self, **kwargs) -> common.Response:
        req = control_service_pb2.ArmRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.Arm, req)
    
    async def disarm(self, **kwargs) -> common.Response:
        req = control_service_pb2.DisarmRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.Disarm, req)

    async def joystick(self, **kwargs) -> common.Response:
        req = control_service_pb2.JoystickRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.Joystick, req)
    
    async def take_off(self, **kwargs) -> common.Response:
        req = control_service_pb2.TakeOffRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.TakeOff, req)
    
    async def land(self, **kwargs) -> common.Response:
        req = control_service_pb2.LandRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.Land, req)
    
    async def hold(self, **kwargs) -> common.Response:
        req = control_service_pb2.HoldRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.Hold, req)
    
    async def kill(self, **kwargs) -> common.Response:
        req = control_service_pb2.KillRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.Kill, req)
    
    async def set_home(self, **kwargs) -> common.Response:
        req = control_service_pb2.SetHomeRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.SetHome, req)
    
    async def return_to_home(self, **kwargs) -> common.Response:
        req = control_service_pb2.ReturnToHomeRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.ReturnToHome, req)
    
    async def set_global_position(self, **kwargs) -> common.Response:
        req = control_service_pb2.SetGlobalPositionRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.SetGlobalPosition, req)
    
    async def set_relative_position(self, **kwargs) -> common.Response:
        req = control_service_pb2.SetRelativePositionRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.SetRelativePosition, req)
    
    async def set_velocity(self, **kwargs) -> common.Response:
        req = control_service_pb2.SetVelocityRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.SetVelocity, req)
    
    async def set_heading(self, **kwargs) -> common.Response:
        req = control_service_pb2.SetHeadingRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.SetHeading, req)
    
    async def set_gimbal_pose(self, **kwargs) -> common.Response:
        req = control_service_pb2.SetGimbalPoseRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_streaming(self.control.SetGimbalPose, req)
    
    async def configure_imaging_sensor_stream(self, **kwargs) -> common.Response:
        req = control_service_pb2.ConfigureImagingSensorStreamRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.ConfigureImagingSensorStream, req)
    
    async def configure_telemetry_stream(self, **kwargs) -> common.Response:
        req = control_service_pb2.ConfigureTelemetryStreamRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.control.ConfigureTelemetryStream, req)
    
    