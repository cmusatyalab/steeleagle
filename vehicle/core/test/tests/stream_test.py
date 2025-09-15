import pytest
import asyncio
from enum import Enum
import zmq
import logging
# Helper import
from helpers import send_requests, Request
# Protocol import
import steeleagle_sdk.protocol.messages.telemetry_pb2 as telemetry_proto
from gabriel_protocol.gabriel_pb2 import ResultWrapper, PayloadType
# Sequencer import
from message_sequencer import Topic

logger = logging.getLogger(__name__)

class Test_Stream:
    '''
    Test class focused on image and telemetry streams.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_streams(self, messages, results, imagery, driver_telemetry, mission_telemetry, gabriel, core):
        expected = {'REMOTE' : 3, 'LOCAL' : 3}
        await imagery.send_multipart([b'imagery', telemetry_proto.Frame().SerializeToString()]),
        await driver_telemetry.send_multipart([b'driver_telemetry', telemetry_proto.DriverTelemetry().SerializeToString()]),
        await mission_telemetry.send_multipart([b'mission_telemetry', telemetry_proto.MissionTelemetry().SerializeToString()])
        received = {'REMOTE' : 0, 'LOCAL' : 0}
        for i in range(6):
            result = ResultWrapper()
            try:
                topic, data = await results.recv_multipart() # This will timeout after one second if nothing is received
                received[topic.decode('utf-8')] += 1
            except Exception as e:
                pass
        assert(expected == received)
