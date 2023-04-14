# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import olympe
from olympe.messages.ardrone3.Piloting import PCMD
import threading
import time
import zmq
import json
import numpy as np


class Avoider(threading.Thread):
    def __init__(self, drone, speed=10, hysteresis=True):
        self.drone = drone
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect('tcp://localhost:5556')
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.speed = max(1, min(speed, 100))
        self.image_size = (640, 480)
        super().__init__()

    def execute_PCMD(self, dpitch, droll):
        print(f"ROLL: {droll}, PITCH: {dpitch}")
        self.drone(PCMD(1, round(droll), round(dpitch), 0, 0, timestampAndSeqNum=0))

    def move_by_offsets(self, vec):
        offset_from_center = self.image_size[0] / 2
        normalized_vec = vec / offset_from_center
        actuation = max(-100, min(normalized_vec * 30, 100))
        self.execute_PCMD(self.speed, actuation)

    def run(self):
        self.tracking = False
        self.active = True

        lastvec = 0
        while self.active:
            try:
                vec = json.loads(self.sub_socket.recv_json(flags=zmq.NOBLOCK))[0]["vector"]
                print(f"Receiving detections: {vec}")
                lastvec = vec
                self.move_by_offsets(vec)
            except Exception as e:
                print(f"Actuating on last: {lastvec}")
                self.move_by_offsets(lastvec)
            time.sleep(0.05)

    def stop(self):
        self.active = False
        self.tracking = False
