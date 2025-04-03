# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import logging
import os
import zmq
from util.utils import setup_socket
from util.utils import SocketOperation
from enum import Enum
from protocol import controlplane_pb2 as control_protocol
from protocol import dataplane_pb2 as data_protocol
from protocol import common_pb2 as common_protocol
from google.protobuf.field_mask_pb2 import FieldMask

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

context = zmq.Context()
cpt_usr_sock = context.socket(zmq.DEALER)
sock_identity = b'usr'
cpt_usr_sock.setsockopt(zmq.IDENTITY, sock_identity)
setup_socket(cpt_usr_sock, SocketOperation.CONNECT, 'CPT_USR_PORT', 'Created command frontend socket endpoint', os.environ.get("DATA_ENDPOINT"))

class ComputeRespond:
    
    def __init__(self):
        self.event = asyncio.Event()
        self.permission = False
        self.result = None
    
    def putResult(self, result):
        self.result = result
        
    def getResult(self):
        return self.result
    
    async def wait(self):
        await self.event.wait()
        
    def set (self):
        self.event.set()
        
class ComputeStub():
    def __init__(self):
        self.seq_num = 1 # set the initial seq_num to 1 caz cnc proto does not support to show 0
        self.seq_num_res = {}
    
    def sender(self, request, computeRespond):
        seq_num = self.seq_num
        logger.info(f"Sending request with seq_num: {seq_num}")
        request.seq_num = seq_num
        self.seq_num += 1
        self.seq_num_res[seq_num] = computeRespond
        serialized_request = request.SerializeToString()
        cpt_usr_sock.send_multipart([serialized_request])
    
    def receiver(self, response_parts):
        if not response_parts:
            logger.error("Received empty response parts")
            return

        response = response_parts[0]
        data_rep = None

        # Try parsing as Compute first
        data_rep = data_protocol.Response()
        data_rep.ParseFromString(response)

        seq_num = data_rep.seq_num
        if seq_num not in self.seq_num_res:
            logger.error(f"Received response with unknown seq_num: {seq_num}")
            return

        data_res_type = data_rep.WhichOneof("type")
        data_res_status = data_rep.resp
        data_res_time = data_rep.timestamp
    
        computeRespond = self.seq_num_res[seq_num]


        if data_res_status == common_protocol.ResponseStatus.FAILED:
            logger.error("STAGE 2: FAILED")
        elif data_res_status == common_protocol.ResponseStatus.COMPLETED:
            logger.info("STAGE 2: COMPLETED")
        
            computeRespond.putResult(data_rep)

        computeRespond.set()
        

    
    async def run(self):
        while True:
            try:
                response_parts = cpt_usr_sock.recv_multipart(flags=zmq.NOBLOCK)
                self.receiver(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                break
            await asyncio.sleep(0)
        
    '''Helper method to send a request and wait for a response'''
    async def send_and_wait(self, request):
        computeRespond = ComputeRespond()
        self.sender(request, computeRespond)
    
        await computeRespond.wait()
        return computeRespond.getResult()
    
    # Get results for a compute engine
    async def getResults(self, compute_key):
        logger.info(f"Getting results for compute type: {compute_key}")
        cpt_req = data_protocol.Request()
        cpt_req.cpt.result_key = compute_key
        result = await self.send_and_wait(cpt_req)
        return result
    
    async def clearResults(self, compute_key):
        logger.info("Clearing results")
        cpt_req = control_protocol.Request()
        cpt_req.cpt.key = compute_key
        cpt_req.cpt.action = control_protocol.ComputeAction.CLEAR
        await self.send_and_wait(cpt_req)


    ''' Telemetry methods '''
    async def getTelemetry(self):
        logger.info("Getting telemetry")
        request = data_protocol.Request()
        request.tel.field_mask = FieldMask()
        rep = await self.send_and_wait(request)
        result = rep.tel
        telDict = {
            "name": None,
            "battery": None,
            "attitude": {"yaw": None, "pitch": None, "roll": None},
            "satellites": None,
            "gps": {"latitude": None, "longitude": None, "altitude": None},
            "relAlt": None,
            "imu": {"forward": None, "right": None, "up": None},
        }
        if result:
            logger.debug(f"Got telemetry: {result}\n")
            telDict["name"] = result.drone_name
            telDict["battery"] = result.battery
            telDict["attitude"]["yaw"] = result.drone_attitude.yaw 
            telDict["attitude"]["pitch"] = result.drone_attitude.pitch
            telDict["attitude"]["roll"] = result.drone_attitude.roll
            telDict["satellites"] = result.satellites
            telDict["gps"]["latitude"] = result.global_position.latitude
            telDict["gps"]["longitude"] = result.global_position.longitude
            telDict["gps"]["altitude"] = result.global_position.altitude
            telDict["relAlt"] = result.relative_position.up
            telDict["imu"]["forward"] = result.velocity.forward_vel
            telDict["imu"]["right"] = result.velocity.right_vel
            telDict["imu"]["up"] = result.velocity.up_vel
            logger.debug(f"finished receiving Telemetry: {telDict}")
            return telDict
        else:
            logger.error("Failed to get telemetry")    
            return None