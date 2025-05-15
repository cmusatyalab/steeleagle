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

    async def wait(self, timeout=None):
        try:
            await asyncio.wait_for(self.event.wait(), timeout)
            return True  # Success
        except asyncio.TimeoutError:
            return False  # Timeout

    def set(self):
        self.event.set()

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
        logger.debug(f"Sending request with seq_num: {seq_num}")
        request.seq_num = seq_num
        self.seq_num += 1
        self.request_map[seq_num] = stub_response

        serialized_request = request.SerializeToString()
        self.sock.send_multipart([serialized_request])

    def parse_response(self, response_parts, response_cls):
        response = response_cls()
        response.ParseFromString(response_parts[0])

        stub_response = self.request_map.get(response.seq_num)
        if not stub_response:
            logger.warning(f"Stale/Unknown seq_num: {response.seq_num} -> Ignored")
            return

        stub_response.put_result(response)
        stub_response.set()

        # Cleanup to avoid memory leak
        del self.request_map[response.seq_num]

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

    async def send_and_wait(self, request, timeout=30.0, retry_limit=4):
        attempt = 0
        while attempt < retry_limit:
            stub_response = StubResponse()
            self.sender(request, stub_response)

            logger.debug(f"Waiting for response... Attempt {attempt + 1}/{retry_limit}")
            responded = await stub_response.wait(timeout=timeout)

            if responded:
                logger.debug(f"Response received for seq_num: {request.seq_num}")
                return stub_response.get_result()
            else:
                logger.warning(f"Timeout waiting for seq_num: {request.seq_num}, retrying...")

                # Mark old request for discard (implicitly done since seq_num won't match)
                attempt += 1

        logger.error(f"Request failed after {retry_limit} attempts.")
        return None
