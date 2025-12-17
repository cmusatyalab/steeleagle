import logging
from google.protobuf.json_format import MessageToDict

# Utility import
from util.config import query_config

# Protocol import
from steeleagle_sdk.protocol.services import remote_service_pb2 as command_proto
from steeleagle_sdk.protocol.services import report_service_pb2 as report_proto
from google.protobuf import any_pb2

# Sequencer import
from test.message_sequencer import MessageSequencer, Topic

logger = logging.getLogger("test/mock_swarm_controller")


class MockSwarmController:
    """
    Provides a fake Swarm Controller to test messaging over ZeroMQ.
    """

    def __init__(self, socket, messages):
        self._socket = socket
        self._seq_num = 0
        self._device = query_config("vehicle.name")
        self.sequencer = MessageSequencer(Topic.SWARM_CONTROLLER, messages)

    async def send_recv_command(self, req_obj):
        """
        Calls a service on the vehicle given a method name, a request object,
        and an empty response prototype. NOTE: This function is not designed
        to be called asynchronously alongside send_recv_command calls.
        """
        self.sequencer.write(req_obj.request)
        any_object = any_pb2.Any()
        any_object.Pack(req_obj.request)
        self._seq_num += 1
        request = command_proto.CommandRequest(
            sequence_number=self._seq_num,
            request=any_object,
            method_name=req_obj.method_name,
            identity=req_obj.identity,
        )

        logger.info("Sending...")
        await self._socket.send_multipart(
            [self._device.encode("utf-8"), request.SerializeToString()]
        )

        complete = False
        logger.info("Receiving...")
        identity, resp_bytes = await self._socket.recv_multipart()
        response = command_proto.CommandResponse()
        response.ParseFromString(resp_bytes)
        logger.info(str(MessageToDict(response)))
        if response.response.status == req_obj.status:
            logger.info(f"Got correct status: {req_obj.status}!")
            complete = True
        self.sequencer.write(response.response)
        return complete

    async def recv_report(self, report_obj):
        """
        Receives a report object from the command socket and checks it against
        a provided report object's report code.
        """
        complete = False
        logger.info("Receiving...")
        identity, resp_bytes = await self._socket.recv_multipart()
        response = report_proto.SendReportRequest()
        response.ParseFromString(resp_bytes)
        logger.info(str(MessageToDict(response)))
        if response.report.report_code == report_obj.report.report_code:
            logger.info(f"Got correct report: {response.report.report_code}!")
            complete = True
        self.sequencer.write(response)
        return complete
