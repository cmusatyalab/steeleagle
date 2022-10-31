import olympe
from olympe.messages.ardrone3.Piloting import TakeOff, Landing, PCMD
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged
from olympe.messages.gimbal import set_target, attitude
from olympe.enums.gimbal import control_mode
from olympe.video.renderer import PdrawRenderer
import threading
import time
import queue
import logging
import subprocess
import cv2
from pynput.keyboard import Listener, Key, KeyCode
from collections import defaultdict
from enum import Enum
from time import sleep
import numpy as np
import math
import os
import zmq
import json
from trackers import dynamic, static, parrot


DRONE_IP = "192.168.42.1" # Real drone IP address
#DRONE_IP = "10.202.0.1" # Simulated drone IP address

class Ctrl(Enum):
    (
        QUIT,
        TAKEOFF,
        LANDING,
        MOVE_LEFT,
        MOVE_RIGHT,
        MOVE_FORWARD,
        MOVE_BACKWARD,
        MOVE_UP,
        MOVE_DOWN,
        TURN_LEFT,
        TURN_RIGHT,
        GIMBAL_UP,
        GIMBAL_DOWN,
        START_TRACK,
        STOP_TRACK
    ) = range(15)


QWERTY_CTRL_KEYS = {
    Ctrl.QUIT: Key.esc,
    Ctrl.TAKEOFF: "t",
    Ctrl.LANDING: "l",
    Ctrl.MOVE_LEFT: "a",
    Ctrl.MOVE_RIGHT: "d",
    Ctrl.MOVE_FORWARD: "w",
    Ctrl.MOVE_BACKWARD: "s",
    Ctrl.MOVE_UP: Key.up,
    Ctrl.MOVE_DOWN: Key.down,
    Ctrl.TURN_LEFT: Key.left,
    Ctrl.TURN_RIGHT: Key.right,
    Ctrl.GIMBAL_UP: "r",
    Ctrl.GIMBAL_DOWN: "f",
    Ctrl.START_TRACK: "b",
    Ctrl.STOP_TRACK: "m"
}

AZERTY_CTRL_KEYS = QWERTY_CTRL_KEYS.copy()
AZERTY_CTRL_KEYS.update(
    {
        Ctrl.MOVE_LEFT: "q",
        Ctrl.MOVE_RIGHT: "d",
        Ctrl.MOVE_FORWARD: "z",
        Ctrl.MOVE_BACKWARD: "s",
    }
)


class KeyboardCtrl(Listener):
    def __init__(self, ctrl_keys=None):
        self._ctrl_keys = self._get_ctrl_keys(ctrl_keys)
        self._key_pressed = defaultdict(lambda: False)
        self._last_action_ts = defaultdict(lambda: 0.0)
        self._current_gimbal_pitch = 0.0
        super().__init__(on_press=self._on_press, on_release=self._on_release)
        self.start()

    def _on_press(self, key):
        if isinstance(key, KeyCode):
            self._key_pressed[key.char] = True
        elif isinstance(key, Key):
            self._key_pressed[key] = True
        if self._key_pressed[self._ctrl_keys[Ctrl.QUIT]]:
            return False
        else:
            return True

    def _on_release(self, key):
        if isinstance(key, KeyCode):
            self._key_pressed[key.char] = False
        elif isinstance(key, Key):
            self._key_pressed[key] = False
        return True

    def quit(self):
        return not self.running or self._key_pressed[self._ctrl_keys[Ctrl.QUIT]]

    def _axis(self, left_key, right_key):
        return 50 * (
            int(self._key_pressed[right_key]) - int(self._key_pressed[left_key])
        )

    def roll(self):
        return self._axis(
            self._ctrl_keys[Ctrl.MOVE_LEFT],
            self._ctrl_keys[Ctrl.MOVE_RIGHT]
        )

    def pitch(self):
        return self._axis(
            self._ctrl_keys[Ctrl.MOVE_BACKWARD],
            self._ctrl_keys[Ctrl.MOVE_FORWARD]
        )

    def yaw(self):
        return self._axis(
            self._ctrl_keys[Ctrl.TURN_LEFT],
            self._ctrl_keys[Ctrl.TURN_RIGHT]
        )


    def _clamp(self, num, min_val, max_val):
        return max(min(num, max_val), min_val)


    def gimbal_pitch(self):
        axis = float(self._axis(
            self._ctrl_keys[Ctrl.GIMBAL_DOWN],
            self._ctrl_keys[Ctrl.GIMBAL_UP]
        ) / 50)
        self._current_gimbal_pitch += axis
        self._clamp(self._current_gimbal_pitch, -90.0, 90.0)
        return axis
    
    def get_gimbal_target(self):
        return self._current_gimbal_pitch

    def throttle(self):
        return self._axis(
            self._ctrl_keys[Ctrl.MOVE_DOWN],
            self._ctrl_keys[Ctrl.MOVE_UP]
        )

    def has_piloting_cmd(self):
        return (
            bool(self.roll())
            or bool(self.pitch())
            or bool(self.yaw())
            or bool(self.throttle())
            or bool(self.gimbal_pitch())
        )

    def _rate_limit_cmd(self, ctrl, delay):
        now = time.time()
        if self._last_action_ts[ctrl] > (now - delay):
            return False
        elif self._key_pressed[self._ctrl_keys[ctrl]]:
            self._last_action_ts[ctrl] = now
            return True
        else:
            return False

    def takeoff(self):
        return self._rate_limit_cmd(Ctrl.TAKEOFF, 2.0)

    def landing(self):
        return self._rate_limit_cmd(Ctrl.LANDING, 2.0)
    
    def start_track(self):
        return self._rate_limit_cmd(Ctrl.START_TRACK, 2.0)

    def stop_track(self):
        return self._rate_limit_cmd(Ctrl.STOP_TRACK, 2.0)

    def _get_ctrl_keys(self, ctrl_keys):
        # Get the default ctrl keys based on the current keyboard layout:
        if ctrl_keys is None:
            ctrl_keys = QWERTY_CTRL_KEYS
            try:
                # Olympe currently only support Linux
                # and the following only works on *nix/X11...
                keyboard_variant = (
                    subprocess.check_output(
                        "setxkbmap -query | grep 'variant:'|"
                        "cut -d ':' -f2 | tr -d ' '",
                        shell=True,
                    )
                    .decode()
                    .strip()
                )
            except subprocess.CalledProcessError:
                pass
            else:
                if keyboard_variant == "azerty":
                    ctrl_keys = AZERTY_CTRL_KEYS
        return ctrl_keys


class OlympeStreaming(threading.Thread):
    def __init__(self, drone, sample_rate=5, model='robomaster'):
        self.drone = drone
        self.sample_rate = sample_rate
        self.model = model
        self.frame_queue = queue.Queue()
        self.flush_queue_lock = threading.Lock()
        self.frame_num = 0 
        self.renderer = None
        super().__init__()
        super().start()

    def start(self):
        self.context = zmq.Context()

        #  Socket to talk to server
        print("Publishing images for OpenScout client's ZmqAdapter..")
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind('tcp://*:5555')

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
        self.renderer = PdrawRenderer(pdraw=self.drone.streaming)

    def stop(self):
        if self.renderer is not None:
            self.renderer.stop()
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

    def send_array(self, A, meta, flags=0, copy=True, track=False):
        """send a numpy array with metadata"""
        md = dict(
            dtype = str(A.dtype),
            shape = A.shape,
            location = {"latitude": meta["latitude"], "longitude": meta["longitude"], "altitude": meta["altitude"]},
            model = self.model,
            gimbal_pitch = meta["gimbal_pitch"],
            heading = meta["heading"]
        )
        self.socket.send_json(md, flags|zmq.SNDMORE)
        return self.socket.send(A, flags, copy=copy, track=track)

    def send_yuv_frame_to_server(self, yuv_frame):
        try:
            # the VideoFrame.info() dictionary contains some useful information
            # such as the video resolution
            info = yuv_frame.info()

            height, width = (  # noqa
                info["raw"]["frame"]["info"]["height"],
                info["raw"]["frame"]["info"]["width"],
            )

            #print(yuv_frame.vmeta()[1])
            gps = drone.get_state(GpsLocationChanged)
            alt = drone.get_state(AltitudeChanged)
            att = drone.get_state(AttitudeChanged)
            gatt = drone.get_state(attitude)
            meta = {"latitude": gps["latitude"], "longitude": gps["longitude"], "altitude": alt["altitude"], "heading": att["yaw"], "gimbal_pitch": gatt[0]["pitch_absolute"]}

            # yuv_frame.vmeta() returns a dictionary that contains additional
            # metadata from the drone (GPS coordinates, battery percentage, ...)
            # convert pdraw YUV flag to OpenCV YUV flag
            cv2_cvt_color_flag = {
                olympe.VDEF_I420: cv2.COLOR_YUV2BGR_I420,
                olympe.VDEF_NV12: cv2.COLOR_YUV2BGR_NV12,
            }[yuv_frame.format()]

            # yuv_frame.as_ndarray() is a 2D numpy array with the proper "shape"
            # i.e (3 * height / 2, width) because it's a YUV I420 or NV12 frame

            # Use OpenCV to convert the yuv frame to RGB
            cv2frame = cv2.cvtColor(yuv_frame.as_ndarray(), cv2_cvt_color_flag)
            cv2frame = cv2.resize(cv2frame, (640, 480))
            if self.frame_num % (30 / self.sample_rate) == 0:
                print(f"Publishing frame {self.frame_num} to OpenScout client...")
                self.send_array(cv2frame, meta)
            self.frame_num += 1
        except Exception as e:
            print("Got an exception", e)

    def run(self):
        main_thread = next(
            filter(lambda t: t.name == "MainThread", threading.enumerate())
        )
        while main_thread.is_alive():
            with self.flush_queue_lock:
                try:
                    yuv_frame = self.frame_queue.get(timeout=0.01)
                except queue.Empty:
                    continue
                try:
                    self.send_yuv_frame_to_server(yuv_frame)
                except Exception as e:
                    #print(e)
                    pass
                finally:
                    # Don't forget to unref the yuv frame. We don't want to
                    # starve the video buffer pool
                    yuv_frame.unref()


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    tracking = False
    tracker = None
    drone = olympe.Drone(DRONE_IP)
    time.sleep(1)
    drone.connect()
    time.sleep(1)
    streamer = OlympeStreaming(drone, model='coco')
    streamer.start()
    control = KeyboardCtrl()
    while not control.quit():
        if control.takeoff():
            drone(TakeOff())
        elif control.landing():
            drone(Landing())
        if control.start_track():
            tracker = dynamic.DynamicLeashTracker(drone, 10.0)
            tracker.start()
            tracking = True
            print("Starting track!")
        elif control.stop_track():
            tracker.stop()
            tracking = False
            print("Stopping track!")
        elif control.has_piloting_cmd() and not tracking:
            drone(
                PCMD(
                    1,
                    control.roll(),
                    control.pitch(),
                    control.yaw(),
                    control.throttle(),
                    timestampAndSeqNum=0
                )
            )
            drone(set_target(0, control_mode.position, "none", 0.0, "absolute", control.get_gimbal_target(), "none", 0.0))
        elif not tracking:
            drone(PCMD(0, 0, 0, 0, 0, timestampAndSeqNum=0))
        time.sleep(0.05)

    drone(Landing()).wait().success()
    drone.disconnect()
