import time
import zmq
import zmq.asyncio
import asyncio
import os
import logging
import yaml
import importlib
import pkgutil
from util.utils import setup_socket, SocketOperation
from cnc_protocol import cnc_pb2
import computes
from kernel.computes.ComputeItf import ComputeInterface
from DataStore import DataStore
from kernel.Service import Service
import sys

# Set up logging
logging_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.INFO), format=logging_format)
logger = logging.getLogger(__name__)

if os.environ.get("LOG_TO_FILE") == "true":
    file_handler = logging.FileHandler('data_service.log')
    file_handler.setFormatter(logging.Formatter(logging_format))
    logger.addHandler(file_handler)


class DataService(Service):
    def __init__(self, config_yaml):
        """Initialize the DataService with sockets, driver handler and compute tasks."""
        super().__init__()

        # Setting up conetxt
        context = zmq.asyncio.Context()
        self.register_context(context)

        # Setting up sockets
        tel_sock = context.socket(zmq.SUB)
        cam_sock = context.socket(zmq.SUB)
        tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
        tel_sock.setsockopt(zmq.CONFLATE, 1)
        cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
        cam_sock.setsockopt(zmq.CONFLATE, 1)
        self.cam_sock = cam_sock
        self.tel_sock = tel_sock
        setup_socket(tel_sock, SocketOperation.BIND, 'TEL_PORT', 'Created telemetry socket endpoint')
        setup_socket(cam_sock, SocketOperation.BIND, 'CAM_PORT', 'Created camera socket endpoint')
        self.register_socket(tel_sock)
        self.register_socket(cam_sock)

        # setting up tasks
        tel_task = asyncio.create_task(self.telemetry_handler())
        cam_task = asyncio.create_task(self.camera_handler())
        self.register_task(tel_task)
        self.register_task(cam_task)

        # setting up data store
        self.data_store = DataStore()
        self.compute_dict = {}
        compute_tasks = self.spawn_computes(config_yaml)
        for task in compute_tasks:
            self.register_task(task)

    ######################################################## USER ##############################################################
    async def compute_setter(self):
        # self.
        pass
    
    async def user_handler(self):
        # self.data_store.get_compute_result()

        pass
    ######################################################## DRIVER ############################################################

    async def telemetry_handler(self):
        """Handles telemetry messages."""
        logger.info("Telemetry handler started")
        while True:
            try:
                msg = await self.tel_sock.recv()
                telemetry = cnc_pb2.Telemetry()
                telemetry.ParseFromString(msg)
                self.data_store.set_raw_data(telemetry)
                logger.debug(f"Received telemetry message after set: {telemetry}")
            except Exception as e:
                logger.error(f"Telemetry handler error: {e}")

    async def camera_handler(self):
        """Handles camera messages."""
        logger.info("Camera handler started")
        while True:
            try:
                msg = await self.cam_sock.recv()
                frame = cnc_pb2.Frame()
                frame.ParseFromString(msg)
                self.data_store.set_raw_data(frame)
                # logger.debug(f"Received camera message after set: {frame}")
                logger.debug(f"Received camera message after set")
            except Exception as e:
                logger.error(f"Camera handler error: {e}")

    ######################################################## COMPUTE ############################################################

    def discover_compute_classes(self):
        """Discover all compute  classes."""
        compute_classes = {}
        for module_info in pkgutil.iter_modules(computes.__path__, computes.__name__ + "."):
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
        return compute_instance, asyncio.create_task(compute_instance.run())

    def spawn_computes(self, config_yaml):
        """Load configuration and spawn computes."""
        config = yaml.safe_load(config_yaml)
        compute_classes = self.discover_compute_classes()
        logger.info(f"Available compute: {', '.join(compute_classes.keys())}")

        compute_tasks = []
        for compute_config in config.get("computes", []):
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

######################################################## MAIN ##############################################################

async def async_main():
    """Main entry point for the DataService."""
    logger.info("Starting DataService")
    config_yaml = os.getenv("CPT_CONFIG")
    if config_yaml is None:
        logger.fatal("Expected CPT_CONFIG env variable to be specified")
        sys.exit(-1)
    data_service = DataService(config_yaml)
    await data_service.start()

if __name__ == "__main__":
    asyncio.run(async_main())
