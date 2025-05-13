import validators
import zmq
import zmq.asyncio
import asyncio
import logging
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol
from service import Service
from util.utils import query_config, setup_logging, SocketOperation
from data_store import DataStore
from google.protobuf.message import DecodeError
import time

logger = logging.getLogger(__name__)
setup_logging(logger, 'hub.logging')

class ControlService(Service):
    def __init__(self, data_store: DataStore, compute_dict):
        """Initialize CommandService and its communication sockets."""
        super().__init__()
        self.compute_dict = compute_dict
        self.data_store = data_store

        # Drone info
        self.drone_id = query_config('driver.id')
        self.drone_type = query_config('driver.type')
        self.manual = True

        # Communication sockets
        self.commander_socket = self.context.socket(zmq.DEALER)
        self.commander_socket.setsockopt(zmq.IDENTITY, self.drone_id.encode('utf-8'))
        self.last_manual_message = None

        self.mission_cmd_socket = self.context.socket(zmq.DEALER)
        self.mission_report_socket = self.context.socket(zmq.DEALER)
        self.driver_socket = self.context.socket(zmq.DEALER)
        self.mission_ctrl_socket = self.context.socket(zmq.REQ)
        

        self.setup_and_register_socket(
            self.commander_socket, SocketOperation.CONNECT,
            'hub.network.cloudlet.commander_to_hub')
        self.setup_and_register_socket(
            self.mission_cmd_socket, SocketOperation.BIND,
            'hub.network.controlplane.mission_to_hub')
        self.setup_and_register_socket(
            self.mission_report_socket, SocketOperation.BIND,
            'hub.network.controlplane.mission_to_hub_2')
        self.setup_and_register_socket(
            self.driver_socket, SocketOperation.BIND,
            'hub.network.controlplane.hub_to_driver')
        self.setup_and_register_socket(
            self.mission_ctrl_socket, SocketOperation.BIND,
            'hub.network.controlplane.hub_to_mission')

        # Start poller loop
        self.create_task(self.cmd_proxy())

    ###########################################################################
    #                              POLLER                                     #
    ###########################################################################
    async def cmd_proxy(self):
        """Unified socket poller handling messages from commander, mission, and driver."""
        logger.info('Command proxy started')
        poller = zmq.asyncio.Poller()
        poller.register(self.commander_socket, zmq.POLLIN)
        poller.register(self.driver_socket, zmq.POLLIN)
        poller.register(self.mission_cmd_socket, zmq.POLLIN)
        poller.register(self.mission_report_socket, zmq.POLLIN)

        while True:
            try:
                socks = dict(await poller.poll())

                if self.commander_socket in socks:
                    self.last_manual_message = time.time()
                    msg = await self.commander_socket.recv_multipart()
                    await self.handle_commander_input(msg[0])
                elif self.last_manual_message and time.time() - self.last_manual_message >= 1:
                    await self.manual_disconnect_failsafe()
                    self.last_manual_message = None

                if self.mission_cmd_socket in socks:
                    msg = await self.mission_cmd_socket.recv_multipart()
                    await self.handle_mission_input(msg[0])
                
                if self.mission_report_socket in socks:
                    msg = await self.mission_report_socket.recv_multipart()
                    await self.handle_mission_report(msg[0])

                if self.driver_socket in socks:
                    msg = await self.driver_socket.recv_multipart()
                    await self.handle_driver_input(msg)

            except Exception as e:
                logger.error(f"cmd_proxy error: {e}")

    ###########################################################################
    #                              HANDLERS                                   #
    ###########################################################################
    async def manual_disconnect_failsafe(self):
        # Stops the drone if the swarm controller disconnects while in manual mode.
        logger.debug("Executing manual disconnection failsafe, ordering the drone to hover!")
        req = control_protocol.Request()
        req.veh.action = control_protocol.VehicleAction.HOVER
        await self.process_vehicle_command(req)

    async def handle_commander_input(self, cmd):
        """Handles command input from the commander."""
        logger.debug(f"Received raw command from commander: {cmd}")
        req = control_protocol.Request()
        req.ParseFromString(cmd)
        logger.info(f"Received command from commander: {req}")
        match req.WhichOneof("type"):
            case "msn":
                await self.process_mission_command(req)
            case "veh":
                await self.process_vehicle_command(req)
            case "cpt":
                logger.info("Received compute command (not implemented)")
                raise NotImplementedError()
            case None:
                raise Exception("Missing request type in commander command")

    async def handle_mission_input(self, cmd):
        """Handles mission request and forwards to driver/commander."""    
        req = control_protocol.Request()
        req.ParseFromString(cmd)
        logger.info(f"Received mission request: {req}")
        match req.WhichOneof("type"):
            case "veh":
                logger.debug(f"Forwarding vehicle command to driver: {req}")
                await self.driver_socket.send_multipart([b'usr', cmd])
            case "cpt":
                logger.info(f"Processing compute control command: {req}")
                match req.cpt.action:
                    case control_protocol.ComputeAction.CLEAR_COMPUTE:
                        await self.clear_compute_result(req)
                    case control_protocol.ComputeAction.CONFIGURE_COMPUTE:
                        await self.configure_compute(req)
                    case _:
                        logger.warning("Unknown compute action from mission input")
            case "msn":
                logger.debug(f"Forwarding mission command to commander: {req}")
                await self.commander_socket.send_multipart([cmd])
            case _:
                logger.warning("Unknown request type in mission message")


    async def handle_mission_report(self, report):
        """Handles mission report and forwards to commander."""
        resp = control_protocol.Response()
        resp.ParseFromString(report)
        logger.info(f"Received patrol report from mission: {resp}")
        await self.commander_socket.send_multipart([report])
   

    async def handle_driver_input(self, msg):
        """Handles message from driver and routes based on identity."""
        logger.debug(f"Received message from driver: {msg}")
        identity, cmd = msg
        if identity == b'usr':
            logger.debug("Forwarding driver response back to mission")
            await self.mission_cmd_socket.send_multipart([cmd])
        elif identity == b'cmdr':
            logger.debug("proxy : driver_socket Received message from BACKEND: discard bc of cmdr")
            pass
        else:
            logger.warning(f"Unknown identity received from driver: {identity}")

    ###########################################################################
    #                              HANDLER HELPERS                            #
    ###########################################################################
    async def process_mission_command(self, req):
        """Processes a mission request from commander."""
        logger.info(f"Mission command received: {req.msn.action}")

        match req.msn.action:
            case control_protocol.MissionAction.DOWNLOAD:
                await self.send_download_mission(req)
                req.msn.action = control_protocol.MissionAction.START
                await self.send_start_mission(req)
                self.manual = False
                self.last_manual_message = None
            case control_protocol.MissionAction.START:
                await self.send_start_mission(req)
                self.manual = False
                self.last_manual_message = None
            case control_protocol.MissionAction.STOP:
                await self.send_stop_mission(req)
                hover = control_protocol.Request()
                hover.veh.action = control_protocol.VehicleAction.HOVER
                asyncio.create_task(self.send_driver_command(hover))
                self.manual = True
            case control_protocol.MissionAction.PATROL:
                await self.send_patrol_area(req)
            case _:
                logger.warning("Unknown mission action")

    async def process_vehicle_command(self, req):
        """Processes a vehicle action in manual mode."""
        if self.manual:
            asyncio.create_task(self.send_driver_command(req))
        else:
            logger.info("Vehicle command ignored (manual mode is disabled)")

    ###########################################################################
    #                             PROCESSORS                                  #
    ###########################################################################

    async def clear_compute_result(self, req):
        logger.info("Clear compute result")
        compute_type = req.cpt.type
        for compute_id in self.compute_dict.keys():
            self.data_store.clear_compute_result(compute_id, compute_type)
            logger.info(f"Cleared compute result for {compute_id} and type {compute_type}")

        reply = control_protocol.Response()
        reply.resp = common_protocol.ResponseStatus.COMPLETED
        reply.timestamp.GetCurrentTime()
        reply.seq_num = req.seq_num
        await self.mission_cmd_socket.send_multipart([reply.SerializeToString()])

    async def configure_compute(self, req):
        logger.info("Configure compute")
        model = req.cpt.model
        lower_bound = [req.cpt.lower_bound.h, req.cpt.lower_bound.s, req.cpt.lower_bound.v]
        upper_bound = [req.cpt.upper_bound.h, req.cpt.upper_bound.s, req.cpt.upper_bound.v]
        for compute_id in self.compute_dict.keys():
            compute = self.compute_dict[compute_id]
            compute.set(model, lower_bound, upper_bound)
            logger.info(f"Configured compute {compute_id} with model {model}, lower_bound {lower_bound}, upper_bound {upper_bound}")

        reply = control_protocol.Response()
        reply.resp = common_protocol.ResponseStatus.COMPLETED
        reply.timestamp.GetCurrentTime()
        reply.seq_num = req.seq_num
        await self.mission_cmd_socket.send_multipart([reply.SerializeToString()])


    async def send_driver_command(self, req):
        """Sends a command to the driver."""
        await self.driver_socket.send_multipart([b'cmdr', req.SerializeToString()])
        logger.info(f"Sent command to driver: {req}")

    async def send_download_mission(self, req):
        """Downloads a mission file via mission_ctrl_socket."""
        if not validators.url(req.msn.url):
            logger.warning(f"Invalid URL: {req.msn.url}")
            return

        logger.info(f"Downloading mission script: {req.msn.url}")
        self.mission_ctrl_socket.send(req.SerializeToString())
        msg = await self.mission_ctrl_socket.recv_multipart()
        rep = control_protocol.Response()
        rep.ParseFromString(msg[0])
        logger.info(f"Download result: {rep.resp}")

    async def send_start_mission(self, req):
        logger.info("Starting mission...")
        self.mission_ctrl_socket.send(req.SerializeToString())
        msg = await self.mission_ctrl_socket.recv_multipart()
        rep = control_protocol.Response()
        rep.ParseFromString(msg[0])
        logger.info(f"Start result: {rep.resp}")

    async def send_stop_mission(self, req):
        logger.info("Stopping mission...")
        self.mission_ctrl_socket.send(req.SerializeToString())
        msg = await self.mission_ctrl_socket.recv_multipart()
        rep = control_protocol.Response()
        rep.ParseFromString(msg[0])
        logger.info(f"Stop result: {rep.resp}")

    async def send_patrol_area(self, req):
        logger.info("Sending patrol area")
        await self.mission_report_socket.send(req.SerializeToString())




