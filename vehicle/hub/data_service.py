import zmq
import zmq.asyncio
import asyncio
import logging
import importlib
import pkgutil
from util.utils import query_config, setup_logging, SocketOperation
import dataplane_pb2 as data_protocol
import datasinks
from datasinks.ComputeItf import ComputeInterface
from data_store import DataStore
from service import Service

logger = logging.getLogger(__name__)

class DataService(Service):
    def __init__(self):
        """Initialize the DataService with sockets, driver handler and compute tasks."""
        super().__init__()

        # Setting up sockets
        self.tel_sock = self.context.socket(zmq.SUB)
        self.cam_sock = self.context.socket(zmq.SUB)
        self.data_reply_sock = self.context.socket(zmq.DEALER)

        self.tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
        self.tel_sock.setsockopt(zmq.CONFLATE, 1)
        self.cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
        self.cam_sock.setsockopt(zmq.CONFLATE, 1)

        self.setup_and_register_socket(self.tel_sock, SocketOperation.BIND, \
                'hub.network.dataplane.driver_to_hub.telemetry')
        self.setup_and_register_socket(self.cam_sock, SocketOperation.BIND, \
                'hub.network.dataplane.driver_to_hub.image_sensor')
        self.setup_and_register_socket(self.data_reply_sock, SocketOperation.BIND, \
                'hub.network.dataplane.hub_to_mission')

        # setting up tasks
        self.create_task(self.telemetry_handler())
        self.create_task(self.camera_handler())
        self.create_task(self.user_handler())

        # setting up data store
        self.data_store = DataStore()
        self.compute_dict = {}
        self.spawn_computes()

    ###########################################################################
    #                                USER                                     #
    ###########################################################################
    def get_result(self, key):
        logger.info(f"Processing getter for {key=}")
        getter_list = []
        for compute_id in self.compute_dict.keys():
            cpt_res = self.data_store.get_compute_result(compute_id, key)

            if cpt_res is None:
                logger.error(f"Result not found for compute_id: {compute_id}")
                continue

            result = data_protocol.ComputeResult()
            result.key = key
            result.frame_id = cpt_res.frame_id
            result.timestamp = cpt_res.timestamp
            # TODO(Aditya): populate DetectionResult and AvoidanceResult
            # instead of using 'generic' result
            result.generic = cpt_res.data

            getter_list.append(result)
            logger.info(f"Sending result: {result} with {compute_id=} {result.timestamp=}")
        return getter_list

    def clear_result(self):
        logger.info("Processing setter")
        for compute_id in self.compute_dict.keys():
            self.data_store.clear_compute_result(compute_id)

    async def user_handler(self):
        """Handles user commands."""
        logger.info("User handler started")
        while True:
            msg = await self.data_reply_sock.recv()
            req = data_protocol.Request()
            req.ParseFromString(msg)

            match req.WhichOneof("type"):
                case "tel":
                    await self.handle_telemetry_req(req)
                case "frame":
                    raise NotImplementedError()
                case "cpt":
                    await self.handle_compute_req(req)
                case None:
                    raise Exception("Expected at least one request type")

    async def handle_compute_req(self, req):
        """Processes a Compute command."""
        logger.info(f"Received compute request: {req}")

        key = req.cpt.key

        cpt_results = self.get_result(key)

        # TODO(Aditya): we could get multiple compute results from different
        # computes, we should extend the proto definition to accomodate this
        # await self.data_reply_sock.send(cpt_command.SerializeToString())
        #
        # Also, a compute request could also involve clearing compute results

    async def handle_telemetry_req(self, req):
        """Processes a telemetry request."""
        logger.info(f"Received telemetry request: {req}")

        tel_data = self.data_store.get_raw_data(req)
        await self.data_reply_sock.send(tel_data.SerializeToString())

    ###########################################################################
    #                                DRIVER                                   #
    ###########################################################################
    async def telemetry_handler(self):
        """Handles telemetry messages."""
        logger.info("Telemetry handler started")
        while True:
            try:
                msg = await self.tel_sock.recv()
                telemetry = data_protocol.Telemetry()
                telemetry.ParseFromString(msg)
                self.data_store.set_raw_data(telemetry)
                logger.debug(f"Received telemetry message after set: {telemetry}")
            except Exception as e:
                logger.error(f"Telemetry handler error: {e}")

    def parse_frame(self, msg):
        """Parses a frame message."""
        frame = data_protocol.Frame()
        frame.ParseFromString(msg)
        return frame

    async def camera_handler(self):
        """Handles camera messages."""
        logger.info("Camera handler started")
        while True:
            try:
                msg = await self.cam_sock.recv()
                # TODO(Aditya): Because of the Python GIL, we should not be
                # doing anything CPU-bound in another thread
                frame = await asyncio.to_thread(self.parse_frame, msg)  # Offload parsing
                self.data_store.set_raw_data(frame, frame.id)
                logger.debug(f"Received camera message after set: {frame}")

            except Exception as e:
                logger.error(f"Camera handler error: {e}")


    ###########################################################################
    #                                COMPUTE                                  #
    ###########################################################################
    def discover_compute_classes(self):
        """Discover all compute  classes."""
        compute_classes = {}
        for module_info in pkgutil.iter_modules(datasinks.__path__, datasinks.__name__ + "."):
            module_name = module_info.name
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, ComputeInterface) and attr is not ComputeInterface:
                    compute_classes[attr_name.lower()] = attr
        return compute_classes

    def run_compute(self, compute_class, compute_id, compute_classes):
        """Instantiate and start a compute ."""
        if compute_class not in compute_classes:
            logger.error(f"compute class '{compute_class}' not found")
            return None

        Compute = compute_classes[compute_class]
        compute_instance = Compute(compute_id, self.data_store)
        logger.info(f"Starting compute {compute_class} with id {compute_id}")
        return compute_instance, self.create_task(compute_instance.run())

    def spawn_computes(self):
        """Load configuration and spawn computes."""
        compute_classes = self.discover_compute_classes()
        logger.info(f"Available compute: {', '.join(compute_classes.keys())}")

        compute_tasks = []

        for compute_config in query_config('hub.computes'):
            compute_class = compute_config["compute_class"].lower()
            compute_id = compute_config["compute_id"]
            result = self.run_compute(compute_class, compute_id, compute_classes)
            if result:
                compute_instance, task = result
                # Store the compute instance and append the compute id to the data store
                self.compute_dict[compute_id] = compute_instance
                self.data_store.append_compute(compute_id)
                compute_tasks.append(task)

        return compute_tasks

async def main():
    """Main entry point for the DataService."""
    setup_logging(logger, 'hub.logging')

    logger.info("Starting DataService")
    await DataService().start()

if __name__ == "__main__":
    asyncio.run(main())
