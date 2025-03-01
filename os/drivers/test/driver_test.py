import asyncio
import logging
import time
from collections import defaultdict
from enum import Enum

import cnc_protocol.cnc_pb2 as cnc_pb2
import zmq
import zmq.asyncio
from pynput.keyboard import Key, KeyCode, Listener
from util.utils import SocketOperation, setup_socket


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
        return not self._key_pressed[self._ctrl_keys[Ctrl.QUIT]]

    def _on_release(self, key):
        if isinstance(key, KeyCode):
            self._key_pressed[key.char] = False
        elif isinstance(key, Key):
            self._key_pressed[key] = False
        return True

    def quit(self):
        return not self.running or self._key_pressed[self._ctrl_keys[Ctrl.QUIT]]

    def _axis(self, left_key, right_key):
        return int(self._key_pressed[right_key]) - int(self._key_pressed[left_key])

    def roll(self):
        return self._axis(self._ctrl_keys[Ctrl.MOVE_LEFT], self._ctrl_keys[Ctrl.MOVE_RIGHT])

    def pitch(self):
        return self._axis(self._ctrl_keys[Ctrl.MOVE_BACKWARD], self._ctrl_keys[Ctrl.MOVE_FORWARD])

    def yaw(self):
        return self._axis(self._ctrl_keys[Ctrl.TURN_LEFT], self._ctrl_keys[Ctrl.TURN_RIGHT])

    def throttle(self):
        return self._axis(self._ctrl_keys[Ctrl.MOVE_DOWN], self._ctrl_keys[Ctrl.MOVE_UP])

    def has_piloting_cmd(self):
        return bool(self.roll()) or bool(self.pitch()) or bool(self.yaw()) or bool(self.throttle())

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
        if ctrl_keys is None:
            ctrl_keys = QWERTY_CTRL_KEYS
        return ctrl_keys


logger = logging.getLogger(__name__)

# Setting up conetxt
context = zmq.asyncio.Context()

cmd_back_sock = context.socket(zmq.DEALER)
setup_socket(
    cmd_back_sock, SocketOperation.BIND, "CMD_BACK_PORT", "Created command backend socket endpoint"
)

tel_sock = context.socket(zmq.SUB)
tel_sock.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all topics
tel_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, SocketOperation.BIND, "TEL_PORT", "Created telemetry socket endpoint")

cam_sock = context.socket(zmq.SUB)
cam_sock.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all topics
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(cam_sock, SocketOperation.BIND, "CAM_PORT", "Created camera socket endpoint")

command_seq = 0


async def recv_telemetry():
    while True:
        try:
            msg = await tel_sock.recv()
            telemetry = cnc_pb2.Telemetry()
            telemetry.ParseFromString(msg)
            logger.debug(f"Received telemetry message after set: {telemetry}")
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Telemetry handler error: {e}")


async def recv_camera():
    while True:
        try:
            msg = await cam_sock.recv()
            frame = cnc_pb2.Frame()
            frame.ParseFromString(msg)
            logger.debug(f"Received camera message after set: {frame}")
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Camera handler error: {e}")


async def send_comm(control):
    global command_seq
    driver_command = cnc_pb2.Driver()
    driver_command.seqNum = command_seq
    command_seq += 1

    if control.takeoff():
        logger.info("Takeoff!")
        driver_command.takeOff = True
    elif control.landing():
        logger.info("Land!")
        driver_command.land = True
    elif control.has_piloting_cmd():
        logger.info(
            f"setVelocity({control.pitch()}, {control.roll()}, {control.throttle()}, {control.yaw()})"
        )
        driver_command.setVelocity.forward_vel = control.pitch()
        driver_command.setVelocity.right_vel = control.roll()
        driver_command.setVelocity.up_vel = control.throttle()
        driver_command.setVelocity.angle_vel = control.yaw()
    else:
        logger.info("Hover.")
        driver_command.hover = True

    message = driver_command.SerializeToString()
    identity = b"cmdr"
    await cmd_back_sock.send_multipart([identity, message])
    logger.info("Sent message.")
    resp = await cmd_back_sock.recv_multipart()


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


async def main():
    control = KeyboardCtrl()
    asyncio.create_task(recv_telemetry())
    while not control.quit():
        await send_comm(control)
        await asyncio.sleep(0.2)


asyncio.run(main())
