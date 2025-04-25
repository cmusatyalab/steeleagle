import asyncio
import logging
import zmq
from util.utils import setup_socket, SocketOperation
logger = logging.getLogger(__name__)


class StubResponse:
    def __init__(self):
        self.event = asyncio.Event()
        self.permission = False
        self.result = None

    def put_result(self, result):
        self.result = result

    def get_result(self):
        return self.result

    async def wait(self):
        await self.event.wait()

    def set(self):
        self.event.set()

    def grant_permission(self):
        self.permission = True

    def check_permission(self):
        return self.permission


class Stub:
    def __init__(self, socket_identity, socket_endpoint):
        self.seq_num = 1
        self.request_map = {}

        context = zmq.Context()
        self.sock = context.socket(zmq.DEALER)
        self.sock.setsockopt(zmq.IDENTITY, socket_identity)
        setup_socket(self.sock, SocketOperation.CONNECT, socket_endpoint)

    def sender(self, request, stub_response):
        seq_num = self.seq_num
        logger.info(f"Sending request with seq_num: {seq_num}")
        request.seq_num = seq_num
        self.seq_num += 1
        self.request_map[seq_num] = stub_response

        serialized_request = request.SerializeToString()
        self.sock.send_multipart([serialized_request])

    async def receiver_loop(self, parse_response_callback):
        while True:
            try:
                response_parts = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                parse_response_callback(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                break
            await asyncio.sleep(0)

    async def send_and_wait(self, request):
        stub_response = StubResponse()
        self.sender(request, stub_response)
        await stub_response.wait()
        return stub_response