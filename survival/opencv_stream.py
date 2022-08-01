import olympe
from olympe.messages.ardrone3.Piloting import TakeOff, moveBy, Landing, moveTo, NavigateHome, PCMD
import threading
import time
import queue
import cv2
import logging
import subprocess
from pynput.keyboard import Listener, Key, KeyCode
from collections import defaultdict
from enum import Enum
from time import sleep
import numpy as np
import math
import os

# from detectors.contour_detector import ContourDetector
# from detectors.particle_analysis import ParticleAnalysis
from detectors.particle_analysis_pytorch import ParticleAnalysis

# DRONE_IP = "192.168.42.1" # Real drone IP address
DRONE_IP = "10.202.0.1" # Simulated drone IP address
a = 1
b = 0.9
c = 0.8
d = 0.7
e = 0.6
f = 0.5
g = 0.4

def calc_dist(p1,p2):
    x1 = p1[0]
    y1 = p1[1]
    x2 = p2[0]
    y2 = p2[1]
    dist = np.sqrt((x2-x1)**2 + (y2-y1)**2)
    return dist


def getChunks(l, n):
    """Yield successive n-sized chunks from l."""
    a = []
    for i in range(0, len(l), n):   
        a.append(l[i:i + n])
    return a

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
    ) = range(11)


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
        return 100 * (
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
    def __init__(self, drone):
        self.drone = drone
        self.frame_queue = queue.Queue()
        self.flush_queue_lock = threading.Lock()
        self.frame_num = 0 
        self.renderer = None
        self.detector = ParticleAnalysis()
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
        #self.renderer = PdrawRenderer(pdraw=self.drone.streaming)

    def start_cb(self):
        pass

    def end_cb(self):
        pass

    def stop(self):
        if self.renderer is not None:
            self.renderer.stop()
        # Properly stop the video stream and disconnect
        self.drone.streaming.stop()

    def yuv_frame_cb(self, yuv_frame):
        """
        This function will be called by Olympe for each decoded YUV frame.
            :type yuv_frame: olympe.VideoFrame
        """
        yuv_frame.ref()
        self.frame_queue.put_nowait(yuv_frame)

    def h264_frame_cb(self, h264_frame):
        pass

    def flush_cb(self, stream):
        if stream["vdef_format"] != olympe.VDEF_I420:
            return True
        with self.flush_queue_lock:
            while not self.frame_queue.empty():
                self.frame_queue.get_nowait().unref()
        return True

    def display_frame(self, yuv_frame):
        # the VideoFrame.info() dictionary contains some useful information
        # such as the video resolution
        info = yuv_frame.info()

        height, width = (  # noqa
            info["raw"]["frame"]["info"]["height"],
            info["raw"]["frame"]["info"]["width"],
        )

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
        frame = cv2.cvtColor(yuv_frame.as_ndarray(), cv2_cvt_color_flag)
        frame = self.detector.detect(frame)

        '''
        StepSize = 5
        currentFrame = 0

        img = frame.copy()
        blur = cv2.bilateralFilter(img,9,40,40)
        edges = cv2.Canny(blur,50,100)
        img_h = img.shape[0] - 1
        img_w = img.shape[1] - 1
        EdgeArray = []

        for j in range(0,img_w,StepSize):
            pixel = (j,0)
            for i in range(img_h-5,0,-1):
                if edges.item(i,j) == 255:
                    pixel = (j,i)
                    break
            EdgeArray.append(pixel)

        for x in range(len(EdgeArray)-1):
            cv2.line(img, EdgeArray[x], EdgeArray[x+1], (0,255,0), 1)

        for x in range(len(EdgeArray)):
            cv2.line(img, (x*StepSize, img_h), EdgeArray[x],(0,255,0),1)

        chunks = getChunks(EdgeArray,int(len(EdgeArray)/3)) # 5
        max_dist = 0
        c = []

        for i in range(len(chunks)-1):
            x_vals = []
            y_vals = []
            for (x,y) in chunks[i]:
                x_vals.append(x)
                y_vals.append(y)
            avg_x = int(np.average(x_vals))
            avg_y = int(np.average(y_vals))
            c.append([avg_y,avg_x])
            cv2.line(frame,(320,480),(avg_x,avg_y),(255,0,0),2)

        print(c)

        forwardEdge = c[1]
        print(forwardEdge)

        cv2.line(frame,(320,480),(forwardEdge[1],forwardEdge[0]),(0,255,0),3)

        y = (min(c))
        print(y)

        if forwardEdge[0] > 250: #200 # >230 works better
            if y[1] < 310:
                #self._ctrl_keys[Ctrl.MOVE_LEFT]
                direction = "left "
                print(direction)

            else: 
                #self._ctrl_keys[Ctrl.MOVE_RIGHT]
                direction = "right "
                print(direction)
        else:
            #self._ctrl_keys[Ctrl.MOVE_FORWARD]
            direction = "forward "
            print(direction)
        '''
        #cv2.imshow("Frames via Detector", frame)
        #cv2.waitKey(1)

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
                    self.display_frame(yuv_frame)
                except Exception as e:
                    print(e)
                finally:
                    # Don't forget to unref the yuv frame. We don't want to
                    # starve the video buffer pool
                    yuv_frame.unref()



logger = logging.getLogger(__name__)

if __name__ == "__main__":
    with olympe.Drone(DRONE_IP) as drone:
        time.sleep(3)
        drone.connect()
        time.sleep(2)
        streamer = OlympeStreaming(drone)
        streamer.start()
        control = KeyboardCtrl()
        while not control.quit():
            if control.takeoff():
                drone(TakeOff())
            elif control.landing():
                drone(Landing())
            if control.has_piloting_cmd():
                drone(
                    PCMD(
                        1,
                        control.roll(),
                        control.pitch(),
                        control.yaw(),
                        control.throttle(),
                        timestampAndSeqNum=0,
                    )
                )
            else:
                drone(PCMD(0, 0, 0, 0, 0, timestampAndSeqNum=0))
            time.sleep(0.05)

    ### Flight commands here ###
    time.sleep(300)
    
    streamer.stop()
     
    drone(Landing()).wait().success()
    drone.disconnect()
