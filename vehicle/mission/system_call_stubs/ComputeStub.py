# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import logging
import os
import zmq
from util.utils import setup_socket
from util.utils import SocketOperation
import controlplane_pb2 as control_protocol
import dataplane_pb2 as data_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)
context = zmq.Context()
data_request_sock = context.socket(zmq.DEALER)
sock_identity = b'usr'
data_request_sock.setsockopt(zmq.IDENTITY, sock_identity)
setup_socket(data_request_sock, SocketOperation.CONNECT, 'hub.network.dataplane.mission_to_hub')


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
        data_request_sock.send_multipart([serialized_request])
    
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
                response_parts = data_request_sock.recv_multipart(flags=zmq.NOBLOCK)
                self.receiver(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                break
            await asyncio.sleep(0)
        
    '''Helper method to send a request and wait for a response'''
    async def send_and_wait(self, request):
        logger.info("Sending request and waiting for response")
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
        request = data_protocol.Request(tel=data_protocol.TelemetryRequest())
        logger.info(f"Requesting telemetry: {request}")
        rep = await self.send_and_wait(request)
        result = rep.tel
        telDict = {
            "name": None,
            "battery": None,
            "satellites": None,
            "gps": {"latitude": None, "longitude": None, "altitude": None},
            "velocity_body": {"forward": None, "right": None, "up": None},
        }
        if result:
            logger.debug(f"Got telemetry: {result}\n")
            telDict["name"] = result.drone_name
            telDict["battery"] = result.battery
            telDict["satellites"] = result.satellites
            telDict["gps"]["latitude"] = result.global_position.latitude
            telDict["gps"]["longitude"] = result.global_position.longitude
            telDict["gps"]["altitude"] = result.global_position.absolute_altitude
            telDict["velocity_body"]["forward"] = result.velocity_body.forward_vel
            telDict["velocity_body"]["right"] = result.velocity_body.right_vel
            telDict["velocity_body"]["up"] = result.velocity_body.up_vel
            telDict["heading"] = result.global_position.heading
            logger.debug(f"finished receiving Telemetry: {telDict}")
            return telDict
        else:
            logger.error("Failed to get telemetry")    
            return None