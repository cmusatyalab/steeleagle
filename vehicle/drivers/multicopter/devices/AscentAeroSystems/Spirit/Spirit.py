# General import
import asyncio
import logging
import threading

# Protocol imports
import common_pb2 as common_protocol

# Streaming imports
import cv2
import dataplane_pb2 as data_protocol

# Interface import
from multicopter.autopilots.ardupilot import ArduPilotDrone

# SDK import (MAVLink)
from pymavlink import mavutil

logger = logging.getLogger(__name__)


class Spirit(ArduPilotDrone):
    # default multicopter mappings
    mode_mapping_acm = {
        "STABILIZE": 0,
        "ACRO": 1,
        "ALT_HOLD": 2,
        "AUTO": 3,
        "GUIDED": 4,
        "LOITER": 5,
        "RTL": 6,
        "CIRCLE": 7,
        "POSITION": 8,
        "LAND": 9,
        "OF_LOITER": 10,
        "DRIFT": 11,
        "SPORT": 13,
        "FLIP": 14,
        "AUTOTUNE": 15,
        "POSHOLD": 16,
        "BRAKE": 17,
        "THROW": 18,
        "AVOID_ADSB": 19,
        "GUIDED_NOGPS": 20,
        "SMART_RTL": 21,
        "FLOWHOLD": 22,
        "FOLLOW": 23,
        "ZIGZAG": 24,
        "SYSTEMID": 25,
        "AUTOROTATE": 26,
        "AUTO_RTL": 27,
    }

    def __init__(self, drone_id, **drone_args):
        super().__init__(drone_id)
        self._streaming_thread = None
        self.url = drone_args.get("video_url", None)

    """ Interface Methods """

    async def get_type(self):
        return "Ascent AeroSytems Spirit"

    async def set_gimbal_pose(self, pose):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def connect(self, connection_string):
        # Connect to drone
        self.vehicle = mavutil.mavlink_connection(connection_string)
        # Wait to connect until we have a mode mapping
        while self._mode_mapping is None:
            self.vehicle.wait_heartbeat()
            self._mode_mapping = self.vehicle.mode_mapping()
            await asyncio.sleep(0.1)

        # override the mode mapping because the mav_type is not reported properly
        # and we end up getting the mappings for a fixed wing
        self._mode_mapping = self.mode_mapping_acm
        # Register telemetry streams
        await self._register_telemetry_streams()
        asyncio.create_task(self._message_listener())
        return True

    async def stream_video(self, cam_sock, rate_hz):
        logger.info("Starting camera stream")
        self._start_streaming(self.url)
        frame_id = 0
        while await self.is_connected():
            try:
                cam_message = data_protocol.Frame()
                frame, frame_shape = await self._get_video_frame()

                if frame is None:
                    logger.error("Failed to get video frame")
                    continue

                cam_message.data = frame
                cam_message.height = frame_shape[0]
                cam_message.width = frame_shape[1]
                cam_message.channels = frame_shape[2]
                cam_message.id = frame_id
                cam_sock.send(cam_message.SerializeToString())
                frame_id = frame_id + 1
            except Exception as e:
                logger.error(f"Failed to get video frame, error: {e}")
            await asyncio.sleep(1 / rate_hz)
        self._stop_streaming()
        logger.info("Camera stream ended, disconnected from drone")

    """ Stream methods """

    def _start_streaming(self, url):
        if not self._streaming_thread:
            self._streaming_thread = StreamingThread(url)
        self._streaming_thread.start()

    async def _get_video_frame(self):
        if self._streaming_thread.is_running:
            return [
                self._streaming_thread.grab_frame().tobytes(),
                self._streaming_thread.get_frame_shape(),
            ]

    def _stop_streaming(self):
        self._streaming_thread.stop()


class StreamingThread(threading.Thread):
    def __init__(self, url):
        threading.Thread.__init__(self)
        self._current_frame = None
        try:
            self.cap = cv2.VideoCapture(url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        except Exception as e:
            logger.error(e)
        self.is_running = True

    def run(self):
        try:
            while self.is_running:
                ret, self._current_frame = self.cap.read()
        except Exception as e:
            logger.error(e)

    def get_frame_shape(self):
        return self._current_frame.shape

    def grab_frame(self):
        try:
            frame = self._current_frame.copy()
            return frame
        except Exception:
            # Send a blank frame
            return None

    def stop(self):
        self.is_running = False
