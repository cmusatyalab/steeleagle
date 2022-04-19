#/usr/bin/python3

# Compatible: Parrot ANAFI / Parrot ANAFI USA/ Parrot ANAFI AI (Untested)
# 
# This is an implementation of the standard MCFCS interface for drones
# compatible with Parrot's Olympe API.
#
# Author: Mihir Bala

from drones.drone import Drone

import math
import time
import queue
import zmq
import cv2
import threading

# Olympe-specific imports
import olympe
from olympe.messages.camera import set_camera_mode, set_photo_mode, take_photo
from olympe.messages.gimbal import set_target, set_offsets, start_offsets_update, stop_offsets_update, offsets, attitude
from olympe.messages.ardrone3.Piloting import TakeOff, moveBy, Landing, moveTo, NavigateHome
from olympe.messages.ardrone3.PilotingSettings import MaxTilt
from olympe.messages.ardrone3.PilotingState import FlyingStateChanged, GpsLocationChanged, SpeedChanged, moveToChanged
import olympe.enums.move as mode
import olympe.enums.camera as camera
import olympe.enums.gimbal as gimbal


class OlympeDrone(Drone):

    def __init__(self, **kwargs):
        self.ip = kwargs["ip"]

    def verify(self): # Check that drone is connected before making command calls.
        if not self.drone:
            raise Exception("Cannot call command on disconnected drone! Hint: did you forget to call connect()?")

    def connect(self):
        self.drone = olympe.Drone(self.ip)
        self.drone.connect()

    def disconnect(self):
        self.verify()
        self.drone.disconnect()

    def takeOff(self):
        self.verify()
        self.drone(TakeOff()).wait().success()

    def land(self):
        self.verify()
        self.drone(Landing()).wait().success()

    def setHome(self, lat, lng):
        self.verify()
        raise Exception("ERROR: Unsupported method for platform Olympe")

    def moveTo(self, lat, lng, alt):
        self.verify()
        self.drone(
            moveTo(lat, lng, alt, mode.orientation_mode.to_target, 0.0)
            >> moveToChanged(latitude=lat, longitude=lng, altitude=alt, orientation_mode=mode.orientation_mode.to_target, status='DONE')
        ).wait().success()

    def moveBy(self, x, y, z):
        self.verify()
        self.drone(moveBy(x, y, z, 0.0)).wait().success()

    def rotateBy(self, theta):
        self.verify()
        self.drone(moveBy(0.0, 0.0, 0.0, theta * math.pi/180.0)).wait().success()
    
    def rotateTo(self, theta):
        raise Exception("ERROR: Unsupported method for platform Olympe")

    # TODO: This only handles gimbal pitch for now!
    def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        self.verify()
        
        self.drone(set_target(
                gimbal_id=0,
                control_mode="position",
                yaw_frame_of_reference="none",
                yaw=yaw_theta,
                pitch_frame_of_reference="absolute",
                pitch=pitch_theta,
                roll_frame_of_reference="none",
                roll=roll_theta,
            )
            >> attitude(pitch_absolute=pitch_theta, _policy="wait", _float_tol=(1e-3, 1e-1))).wait().success()

    def takePhoto(self):
        self.verify()
        self.drone(set_camera_mode(0, camera.camera_mode.photo)).wait().success()
        self.drone(set_photo_mode(0,
                camera.photo_mode.single,
                camera.photo_format.full_frame,
                camera.photo_file_format.jpeg,
                camera.burst_value.burst_14_over_4s,
                camera.bracketing_preset.preset_1ev,
                0.0)).wait().success()
        self.drone(take_photo(0)).wait().success()
        self.drone(set_camera_mode(0, camera.camera_mode.recording)).wait().success()

    def getStatus(self):
        self.verify()
        airspeed = 0
        loc = {}
        state = ""
        try:
            speed = drone.get_state(SpeedChanged)
            airspeed = math.sqrt(speed["speedX"]**2 + speed["speedY"]**2 + speed["speedZ"]**2)
        except:
            pass
        try:
            loc = self.drone.get_state(GpsLocationChanged)
            state = self.drone.get_state(FlyingStateChanged)
        except:
            pass

        payload = {"location": loc, "state" : state["state"].name, "airspeed" : airspeed}
        return payload

    def cancel(self):
        self.verify()
        # TODO: Cancel the current command that the drone is executing.

    # *** STREAMING CODE ***
    def startStreaming(self, q_size=10, sr=2):
        self.frame_queue = queue.Queue
        self.streaming_obj = OlympeStreaming(self.drone, self.frame_queue, q_size, sr)
        self.streaming_obj.start()

    def stopStreaming(self):
        self.streaming_obj.stop()

    def getVideoFrame(self):
        self.verify()
        if not self.is_streaming:
            raise Exception("Cannot get video frame from non-streaming drone! Hint: did you forget to call startStreaming()?")
        try:
            yuv_frame = self.frame_queue.get_nowait()
            info = yuv_frame.info()
            height, width = (
                info["raw"]["frame"]["info"]["height"],
                info["raw"]["frame"]["info"]["width"],
            )

            # Convert PDraw YUV flag to OpenCV YUV flag
            cv2_cvt_color_flag = {
                olympe.VDEF_I420: cv2.COLOR_YUV2BGR_I420,
                olympe.VDEF_NV12: cv2.COLOR_YUV2BGR_NV12,
            }[yuv_frame.format()]

            # Use OpenCV to convert the yuv frame to RGB
            cv2frame = cv2.cvtColor(yuv_frame.as_ndarray(), cv2_cvt_color_flag)
            return cv2frame
        except: # If no frame is available, send back none
            return None

    # Streaming class that handles pulling frames from the drone.
    class OlympeStreaming(threading.Thread):
        def __init__(self, drone, queue, max_q_size, sample_rate):
            self.drone = drone
            self.frame_queue = queue
            self.max_q_size = max_q_size
            self.flush_queue_lock = threading.Lock()
            self.frame_num = 0 
            self.sample_rate = sample_rate
            super().__init__()
            super().start()
    
        def start(self):
            # Setup your callback functions to do some live video processing
            self.drone.streaming.set_callbacks(
                raw_cb=self.yuv_frame_cb,
                h264_cb=self.h264_frame_cb,
                start_cb=self.start_cb,
                end_cb=self.end_cb,
                flush_raw_cb=self.flush_cb,
            )
            # Start video streaming
            self.drone.streaming.start()
    
        def stop(self):
            # Properly stop the video stream and disconnect
            self.drone.streaming.stop()
            self.context.destroy()
    
        def yuv_frame_cb(self, yuv_frame):
            """
            This function will be called by Olympe for each decoded YUV frame.
                :type yuv_frame: olympe.VideoFrame
            """
            yuv_frame.ref()
            self.frame_queue.put_nowait(yuv_frame)
            if self.frame_queue.qsize > self.max_q_size:
                self.frame_queue.get_nowait().unref()
    
        def flush_cb(self, stream):
            if stream["vdef_format"] != olympe.VDEF_I420:
                return True
            with self.flush_queue_lock:
                while not self.frame_queue.empty():
                    self.frame_queue.get_nowait().unref()
            return True
    
        def start_cb(self):
            pass
    
        def end_cb(self):
            pass
    
        def h264_frame_cb(self, h264_frame):
            pass
    
