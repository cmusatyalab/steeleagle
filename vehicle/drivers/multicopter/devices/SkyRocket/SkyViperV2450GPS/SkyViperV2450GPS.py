# General import
import logging
# Interface import
from multicopter.autopilots.ardupilot import ArduPilotDrone
# Protocol imports
from protocol import dataplane_pb2 as data_protocol
import asyncio

logger = logging.getLogger(__name__)

class SkyViperV2450GPSDrone(ArduPilotDrone):
    
    ''' Interface Methods '''
    async def get_type(self):
        return "SkyRocket SkyViper v2450 GPS"

    async def stream_video(self, cam_sock):
        logger.info('Starting camera stream')
        self._start_streaming(self.url)
        frame_id = 0
        while await self.is_connected():
            try:
                cam_message = data_protocol.Frame()
                frame, frame_shape = await self._get_video_frame()
                
                if frame is None:
                    logger.error('Failed to get video frame')
                    continue
                
                cam_message.data = frame
                cam_message.height = frame_shape[0]
                cam_message.width = frame_shape[1]
                cam_message.channels = frame_shape[2]
                cam_message.id = frame_id
                cam_sock.send(cam_message.SerializeToString())
                frame_id = frame_id + 1
            except Exception as e:
                logger.error(f'Failed to get video frame, error: {e}')
            await asyncio.sleep(0.033)
        self._stop_streaming()
        logger.info("Camera stream ended, disconnected from drone")
    
    
    async def set_gimbal_pose(self, pose):
        pass
    
    
    ''' Stream methods '''
    async def _start_streaming(self):
        if not self._streaming_thread:
            self._streaming_thread = StreamingThread()
        self._streaming_thread.start()

    async def _get_video_frame(self):
        if self._streaming_thread.is_running:
            return [self._streaming_thread.grab_frame().tobytes(), self._streaming_thread.get_frame_shape()]

    async def _stop_streaming(self):
        self._streaming_thread.stop()
        
# Streaming imports
import cv2
import numpy as np
import os
import threading

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
            while(self.is_running):
                ret, self._current_frame = self.cap.read()
        except Exception as e:
            logger.error(e)
            
    def get_frame_shape(self):
        return self._current_frame.shape
    
    def grab_frame(self):
        try:
            frame = self._current_frame.copy()
            return frame
        except Exception as e:
            # Send a blank frame
            return None

    def stop(self):
        self.is_running = False
