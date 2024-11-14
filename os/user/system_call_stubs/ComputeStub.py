# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import logging
import os
import zmq
from cnc_protocol import cnc_pb2
from util.utils import setup_socket

# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

# context = zmq.Context()
# cpt_sock = context.socket(zmq.REQ)
# setup_socket(cpt_sock, 'connect', 'CPT_PORT', 'Connected to compute socket endpoint', os.environ.get("DATA_ENDPOINT"))

# class ComputeStub():
#     # REQ/REP function
#     async def sendRecv(self, data):
#         request = data
#         cpt_sock.send(data.SerializeToString())
#         response = await cpt_sock.recv()
#         return response

#     # Switch the model used for computation
#     async def setParams(self, model, hsv_lower, hsv_upper):
#         req = cnc_pb2.ComputeParams()
#         if model:
#             req.model = model
#         if hsv_lower:
#             req.hsv_lower_bound.H = hsv_lower[0]
#             req.hsv_lower_bound.S = hsv_lower[1]
#             req.hsv_lower_bound.V = hsv_lower[2]
#         if hsv_upper:
#             req.hsv_upper_bound.H = hsv_upper[0]
#             req.hsv_upper_bound.S = hsv_upper[1]
#             req.hsv_upper_bound.V = hsv_upper[2]
#         await self.sendRecv(req)

#     # Get results for a compute engine
#     async def getResults(self, engine_key, invalidate_cache=True):
#         req = cnc_pb2.ComputeRequest()
#         req.engineKey = engine_key
#         req.invalidateCache = invalidate_cache
#         resp = await self.sendRecv(req)
#         msg = cnc_pb2.ComputeResult()
#         msg.ParseFromString(resp)
#         return msg.result

