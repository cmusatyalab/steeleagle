# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import json
import threading
import time

import numpy as np
import zmq
from olympe.enums.gimbal import control_mode
from olympe.messages.ardrone3.Piloting import PCMD
from olympe.messages.ardrone3.PilotingState import AltitudeChanged
from olympe.messages.gimbal import set_target


class StaticLeashTracker(threading.Thread):
    def __init__(self, drone, leash=20.0):
        self.drone = drone
        self.leash = leash
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect('tcp://localhost:5556')
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.image_res = (640, 480)
        self.pixel_center = (self.image_res[0] / 2, self.image_res[1] / 2)
        self.HFOV = 69
        self.VFOV = 43
        super().__init__()

    def set_leash(self):
        alt = self.drone.get_state(AltitudeChanged)["altitude"]
        print(alt)
        print(self.leash)
        print(np.arctan(self.leash/alt))
        angle = -1 * (90 - (np.arctan(self.leash / alt) * (180 / np.pi)))
        print(angle)
        self.drone(set_target(0, control_mode.position, "none", 0.0, "absolute", angle, "none", 0.0))

    def pitch_step_func(self, p):
        CUTOFFS = [0.0, 0.35, 0.45, 0.55, 0.65, 1.0]
        SPEEDS = [-30, -10, 0, 10, 30]

        if CUTOFFS[0] < p and p < CUTOFFS[1]:
            return SPEEDS[0]
        elif CUTOFFS[1] < p and p < CUTOFFS[2]:
            return SPEEDS[1]
        elif CUTOFFS[2] < p and p < CUTOFFS[3]:
            return SPEEDS[2]
        elif CUTOFFS[3] < p and p < CUTOFFS[4]:
            return SPEEDS[3]
        elif CUTOFFS[4] < p and p < CUTOFFS[5]:
            return SPEEDS[4]

    def roll_step_func(self, r):
        CUTOFFS = [0.0, 0.35, 0.45, 0.55, 0.65, 1.0]
        SPEEDS = [-30, -10, 0, 10, 30]

        if CUTOFFS[0] < r and r < CUTOFFS[1]:
            return SPEEDS[0]
        elif CUTOFFS[1] < r and r < CUTOFFS[2]:
            return SPEEDS[1]
        elif CUTOFFS[2] < r and r < CUTOFFS[3]:
            return SPEEDS[2]
        elif CUTOFFS[3] < r and r < CUTOFFS[4]:
            return SPEEDS[3]
        elif CUTOFFS[4] < r and r < CUTOFFS[5]:
            return SPEEDS[4]

    def calculate_offsets(self, box):
        target_x_percentage = ((box[3] - box[1]) / 2.0) + box[1] 
        roll_speed = self.roll_step_func(target_x_percentage)
        target_y_percentage = 1 - (((box[2] - box[0]) / 2.0) + box[0])
        pitch_speed = self.pitch_step_func(target_y_percentage)

        return roll_speed, pitch_speed

    def execute_PCMD(self, roll, pitch):
        self.drone(PCMD(1, roll, pitch, 0, 0, timestampAndSeqNum=0))

    def run(self):
        self.tracking = False
        self.active = True
        self.set_leash()

        while self.active:
            try:
                det = json.loads(self.sub_socket.recv_json())
                if len(det) > 0:
                    if not self.tracking:
                        print("Starting new track on object: \"{0}\"".format(det[0]["class"]))
                    else:
                        print(f"Got detection from the cloudlet: {det}")
                    self.tracking = True
                    roll, pitch = self.calculate_offsets(det[0]["box"])
                    self.execute_PCMD(roll, pitch)
            except Exception as e:
                print(f"Exception: {e}")
            time.sleep(0.05)

    def stop(self):
        self.active = False
        self.tracking = False
