# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import json
import threading
import time

import zmq
from olympe.messages.ardrone3.Piloting import PCMD
from olympe.messages.ardrone3.PilotingState import GpsLocationChanged

FOLDER = "./avoidance/traces/"


class MiDaSAvoider(threading.Thread):
    def __init__(self, drone, speed=5, hysteresis=True):
        self.drone = drone
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect("tcp://localhost:5556")
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.speed = max(1, min(speed, 100))
        self.hysteresis = hysteresis
        self.image_size = (640, 480)
        super().__init__()

    def execute_PCMD(self, dpitch, droll):
        print(f"ROLL: {droll}, PITCH: {dpitch}")
        self.drone(PCMD(1, round(droll), round(dpitch), 0, 0, timestampAndSeqNum=0))

    def move_by_offsets(self, vec):
        offset_from_center = self.image_size[0] / 2
        normalized_vec = max(-1.0, min(vec / offset_from_center, 1.0))
        actuation = max(-100, min(normalized_vec * 30, 100))
        self.execute_PCMD(self.speed, actuation)

    def run(self):
        self.tracking = False
        self.active = True

        # trace = open(FOLDER + datetime.now().strftime("%m-%d-%Y-%H-%M-%S") + ".txt", 'a')
        # print("Writing trace!")

        lastvec = 0
        while self.active:
            gps = self.drone.get_state(GpsLocationChanged)
            lat = gps["latitude"]
            lng = gps["longitude"]
            # trace.write(f"{lat}, {lng}" + '\n')
            print("Wrote coordinates.")
            try:
                vec = json.loads(self.sub_socket.recv_json(flags=zmq.NOBLOCK))[0]["vector"]
                print(f"Receiving detections: {vec}")
                diff = vec - lastvec if self.hysteresis else 0
                lastvec = vec
                self.move_by_offsets(vec + diff)
            except Exception:
                print(f"Actuating on last: {lastvec}")
                self.move_by_offsets(lastvec)
            time.sleep(0.05)

        # trace.close()

    def stop(self):
        self.active = False
        self.tracking = False
