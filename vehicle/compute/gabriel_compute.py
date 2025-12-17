import asyncio
import logging
import time
import cv2
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_client.zeromq_client import ProducerWrapper, ZeroMQClient
from gabriel_server import cognitive_engine
from datasinks.ComputeItf import ComputeInterface
from hub.data_store import DataStore
import dataplane_pb2 as data_protocol
import controlplane_pb2 as control_protocol
import gabriel_extras_pb2 as gabriel_extras
from util.utils import query_config

logger = logging.getLogger(__name__)


class GabrielCompute(ComputeInterface):
    def __init__(self, compute_id, data_store: DataStore):
        super().__init__(compute_id)

        self.drone_id = query_config("driver.id")

        # remote computation parameters
        self.set_params = {"model": "coco", "hsv_lower": None, "hsv_upper": None}

        # Gabriel
        self.server = query_config("hub.network.cloudlet.endpoint")
        self.port = query_config("hub.network.cloudlet.hub_to_gabriel")

        logger.info(f"Gabriel compute: Gabriel server: {self.server}")
        logger.info(f"Gabriel compute: Gabriel port: {self.port}")
        self.engine_results = {}
        self.drone_registered = False
        self.gabriel_client = ZeroMQClient(
            self.server,
            self.port,
            [self.get_telemetry_producer(), self.get_frame_producer()],
            self.process_results,
        )

        # data_store
        self.data_store = data_store
        self.frame_ts = -1

    async def run(self):
        logger.info("Gabriel compute: launching Gabriel client")
        await self.gabriel_client.launch_async()

    def set(self, model, hsv_lower, hsv_upper):
        self.set_params["model"] = model
        self.set_params["hsv_lower"] = hsv_lower
        self.set_params["hsv_upper"] = hsv_upper

    def stop(self):
        """Stopping the worker."""
        pass

    def get_status(self):
        """Getting the status of the worker."""
        return self.compute_status

    ###########################################################################
    #                           GABRIEL COMPUTE                               #
    ###########################################################################
    def process_results(self, result_wrapper):
        if len(result_wrapper.results) != 1:
            return

        response = cognitive_engine.unpack_extras(
            control_protocol.Response, result_wrapper
        )
        for result in result_wrapper.results:
            if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                payload = result.payload.decode("utf-8")
                try:
                    if len(payload) != 0:
                        # get engine id
                        compute_type = result_wrapper.result_producer_name.value

                        # get timestamp
                        timestamp = time.time()
                        # update
                        if compute_type == "openscout_object":
                            logger.info(
                                f"Gabriel compute: {timestamp=}, {compute_type=}, {result=}"
                            )
                        logger.debug(
                            f"Gabriel compute: {timestamp=}, {compute_type=}, {result=}"
                        )
                        self.data_store.update_compute_result(
                            self.compute_id,
                            compute_type,
                            payload,
                            response.seq_num,
                            timestamp,
                        )
                except Exception as e:
                    logger.error(
                        f"Gabriel compute process_results: error processing result: {e}"
                    )
            else:
                logger.debug(f"Got result type {result.payload_type}. Expected TEXT.")

    def get_frame_producer(self):
        async def producer():
            await asyncio.sleep(0.1)
            self.compute_status = self.ComputeStatus.Connected

            logger.debug(f"Frame producer: starting {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            frame_data = data_protocol.Frame()

            entry = self.data_store.get_raw_data(frame_data)
            # Wait for a new frame
            while entry is None or entry.timestamp <= self.frame_ts:
                if entry is None:
                    logger.debug("Waiting for new frame from driver, entry is none!")
                else:
                    logger.debug(
                        f"Waiting for new frame from driver, {entry.timestamp} <= {self.frame_ts}"
                    )
                await self.data_store.wait_for_new_data(type(frame_data))
                entry = self.data_store.get_raw_data(frame_data)
            self.frame_ts = entry.timestamp

            tel_data = data_protocol.Telemetry()
            self.data_store.get_raw_data(tel_data)
            try:
                if (
                    frame_data is not None
                    and frame_data.data != b""
                    and tel_data is not None
                ):
                    logger.debug(
                        f"New frame frame_id={frame_data.id} available from driver, tel_data={tel_data}"
                    )

                    frame_bytes = frame_data.data

                    nparr = np.frombuffer(frame_bytes, dtype=np.uint8)
                    frame = cv2.imencode(
                        ".jpg",
                        nparr.reshape(
                            frame_data.height, frame_data.width, frame_data.channels
                        ),
                    )[1]
                    input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                    input_frame.payloads.append(frame.tobytes())

                    # produce extras
                    extras = gabriel_extras.Extras()
                    compute_command = extras.cpt_request

                    if self.set_params["model"] is not None:
                        compute_command.cpt.model = self.set_params["model"]
                    if self.set_params["hsv_lower"] is not None:
                        compute_command.cpt.lower_bound.h = self.set_params[
                            "hsv_lower"
                        ][0]
                        compute_command.cpt.lower_bound.s = self.set_params[
                            "hsv_lower"
                        ][1]
                        compute_command.cpt.lower_bound.v = self.set_params[
                            "hsv_lower"
                        ][2]
                    if self.set_params["hsv_upper"] is not None:
                        compute_command.cpt.upper_bound.h = self.set_params[
                            "hsv_upper"
                        ][0]
                        compute_command.cpt.upper_bound.s = self.set_params[
                            "hsv_upper"
                        ][1]
                        compute_command.cpt.upper_bound.v = self.set_params[
                            "hsv_upper"
                        ][2]

                    self.data_store.get_raw_data(extras.telemetry)

                    if compute_command is not None:
                        input_frame.extras.Pack(extras)
                else:
                    logger.info("Gabriel compute Frame producer: frame is None")
                    input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                    input_frame.payloads.append(
                        "Streaming not started, no frame to show.".encode("utf-8")
                    )
            except Exception as e:
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append(
                    "Unable to produce a frame!".encode("utf-8")
                )
                logger.info(
                    f"Gabriel compute Frame producer: unable to produce a frame: {e}"
                )

            logger.debug(f"Gabriel compute Frame producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name="telemetry")

    def get_telemetry_producer(self):
        async def producer():
            await asyncio.sleep(0.1)

            self.compute_status = self.ComputeStatus.Connected
            logger.debug(f"tel producer: starting time {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append("heartbeart".encode("utf8"))
            tel_data = data_protocol.Telemetry()
            ret = self.data_store.get_raw_data(tel_data)

            try:
                if ret is not None:
                    extras = gabriel_extras.Extras()
                    extras.telemetry.CopyFrom(tel_data)
                    logger.debug(
                        f"Gabriel compute telemetry producer: sending telemetry; drone_name={tel_data.drone_name}"
                    )
                    # Register when we start sending telemetry
                    if not self.drone_registered and len(tel_data.drone_name) > 0:
                        logger.info(
                            "Gabriel compute telemetry producer: sending registration request to backend"
                        )
                        extras.registering = True
                        self.drone_registered = True
                        tel_data.uptime.FromSeconds(0)
                    else:
                        logger.debug(
                            "Gabriel compute telemetry producer: sending telemetry"
                        )
                        # Send telemetry
                        extras.registering = False
                    input_frame.extras.Pack(extras)
                    logger.debug(
                        f"Gabriel compute telemetry producer: sending Gabriel telemetry! content: {extras}"
                    )
                else:
                    logger.error("Telemetry unavailable")
            except Exception as e:
                logger.error(f"Gabriel compute telemetry producer: {e}")
            logger.debug(f"tel producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name="telemetry")
