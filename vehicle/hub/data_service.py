import zmq
import zmq.asyncio
import asyncio
import logging
from util.utils import query_config, setup_logging, SocketOperation
import dataplane_pb2 as data_protocol
import common_pb2 as common_protocol
from service import Service
from data_store import DataStore

logger = logging.getLogger(__name__)
setup_logging(logger, 'hub.logging')

# Bandaid fix to prevent logs from being polluted by WRONG_INPUT_FORMAT errors.
class WrongInputFormatFilter(logging.Filter):
    def filter(self, record):
        return "WRONG_INPUT_FORMAT" not in record.getMessage()

logging.getLogger('gabriel_client.zeromq_client').addFilter(WrongInputFormatFilter())

class DataService(Service):
    def __init__(self, data_store: DataStore, compute_dict):
        """Initialize the DataService with sockets and compute tasks."""
        super().__init__()
        self.data_store = data_store
        self.compute_dict = compute_dict

        # Setting up sockets
        self.tel_sock = self.context.socket(zmq.SUB)
        self.cam_sock = self.context.socket(zmq.SUB)
        self.data_reply_sock = self.context.socket(zmq.DEALER)

        self.tel_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
        self.tel_sock.setsockopt(zmq.CONFLATE, 1)
        self.cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
        self.cam_sock.setsockopt(zmq.CONFLATE, 1)

        self.setup_and_register_socket(
            self.tel_sock, SocketOperation.BIND,
            'hub.network.dataplane.driver_to_hub.telemetry')
        self.setup_and_register_socket(
            self.cam_sock, SocketOperation.BIND,
            'hub.network.dataplane.driver_to_hub.image_sensor')
        self.setup_and_register_socket(
            self.data_reply_sock, SocketOperation.BIND,
            'hub.network.dataplane.mission_to_hub')

        # Unified poller task
        self.create_task(self.data_proxy())

    ###########################################################################
    #                              POLLER                                     #
    ###########################################################################
    async def data_proxy(self):
        logger.info("DataService poller started")
        poller = zmq.asyncio.Poller()
        poller.register(self.tel_sock, zmq.POLLIN)
        poller.register(self.cam_sock, zmq.POLLIN)
        poller.register(self.data_reply_sock, zmq.POLLIN)

        while True:
            try:
                socks = dict(await poller.poll())

                if self.tel_sock in socks:
                    msg = await self.tel_sock.recv()
                    await self.handle_telemetry_input(msg)

                if self.cam_sock in socks:
                    msg = await self.cam_sock.recv()
                    await self.handle_camera_input(msg)

                if self.data_reply_sock in socks:
                    msg = await self.data_reply_sock.recv()
                    await self.handle_user_request(msg)

            except Exception as e:
                logger.error(f"Poller error in DataService: {e}")

    ###########################################################################
    #                              HANDLERS                                   #
    ###########################################################################
    async def handle_telemetry_input(self, msg):
        """Handles incoming telemetry messages from the driver."""
        try:
            telemetry = data_protocol.Telemetry()
            telemetry.ParseFromString(msg)
            self.data_store.set_raw_data(telemetry)
            logger.debug(f"Received telemetry message: {telemetry}")
        except Exception as e:
            logger.error(f"Telemetry handler error: {e}")

    async def handle_camera_input(self, msg):
        """Handles incoming camera messages from the driver."""
        try:
            # Offload decoding to a thread to avoid blocking event loop
            frame = await asyncio.to_thread(self.parse_frame, msg)
            self.data_store.set_raw_data(frame, frame.id)
            logger.debug(f"Received camera frame ID={frame.id}")
        except Exception as e:
            logger.error(f"Camera handler error: {e}")

    async def handle_user_request(self, msg):
        """Handles compute/telemetry/frame requests from mission layer."""
        req = data_protocol.Request()
        req.ParseFromString(msg)
        logger.debug(f"Received user request: {req}")

        match req.WhichOneof("type"):
            case "tel":
                await self.process_telemetry_req(req)
            case "frame":
                raise NotImplementedError()
            case "cpt":
                await self.process_compute_req(req)
            case None:
                raise Exception("Expected at least one request type")


    ###########################################################################
    #                              PROCESSORS                                 #
    ###########################################################################
    def parse_frame(self, msg):
        """Parses a frame message (done in thread pool)."""
        frame = data_protocol.Frame()
        frame.ParseFromString(msg)
        return frame

    async def process_telemetry_req(self, req):
        """Processes a telemetry request."""
        logger.debug(f"Handling telemetry request: {req}")
        tel_data = data_protocol.Telemetry()
        ret = self.data_store.get_raw_data(tel_data)

        resp = data_protocol.Response()
        if ret is None:
            resp.resp = common_protocol.ResponseStatus.FAILED
        else:
            resp.resp = common_protocol.ResponseStatus.COMPLETED
            resp.tel.CopyFrom(tel_data)

        resp.timestamp.GetCurrentTime()
        resp.seq_num = req.seq_num
        logger.debug(f"Sending telemetry response: {resp}")

        await self.data_reply_sock.send_multipart([resp.SerializeToString()])

    async def process_compute_req(self, req):
        """Processes a compute result request and replies with results."""
        logger.debug(f"Handling compute request: {req}")
        compute_type = req.cpt.type
        response = data_protocol.Response()

        for compute_id in self.compute_dict.keys():
            cpt_res = self.data_store.get_compute_result(compute_id, compute_type)
            if cpt_res is None:
                logger.warning(f"No result for {compute_id}")
                continue

            compute_result = data_protocol.ComputeResult()
            compute_result.generic_result = cpt_res.data
            response.cpt.result.append(compute_result)
            logger.debug(f"Appending result for {compute_id}: {compute_result}")

        response.timestamp.GetCurrentTime()
        response.seq_num = req.seq_num
        logger.debug(f"Sending compute response: {response}")
        await self.data_reply_sock.send_multipart([response.SerializeToString()])
