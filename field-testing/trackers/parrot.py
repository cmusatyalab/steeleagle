# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import json
import threading
import time

import numpy as np
import olympe.messages.follow_me as follow_me
import zmq
from geopy.distance import geodesic as GD
from olympe.enums.follow_me import mode
from olympe.messages.ardrone3.PilotingState import (
    AltitudeChanged,
    GpsLocationChanged,
)


class ParrotFollowMeTracker(threading.Thread):
    def __init__(self, drone, mode=mode.look_at):
        self.drone = drone
        self.behavior = mode
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect('tcp://localhost:5556')
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
        super().__init__()

    def calculate_azimuth_elevation(self, target_lat, target_lon):
        gps = self.drone.get_state(GpsLocationChanged)
        alt = self.drone.get_state(AltitudeChanged)
        
        # Elevation calculation
        d = GD((target_lat, target_lon), (gps["latitude"], gps["longitude"]))
        elev = np.arctan(alt["altitude"] / d.m)

        # Azimuth calculation
        target_lat = target_lat * (np.pi * 180)
        drone_lat = gps["latitude"] * (np.pi * 180)
        delta_lon = (gps["longitude"] - target_lon) * (np.pi * 180)
        y = np.sin(delta_lon) * np.cos(drone_lat)
        x = np.cos(target_lat) * np.sin(drone_lat) - np.sin(target_lat) * np.cos(drone_lat) * np.cos(delta_lon)
        azi = np.arctan2(y, x)

        return azi, elev

    def current_time_millis(self):
        return round(time.time() * 1000)

    def run(self):
        self.tracking = False
        self.active = True
        self.start = None

        while self.active:
            try:
                det = json.loads(self.sub_socket.recv_json())
                if not self.tracking and len(det) > 0:
                    print("Starting new track on object: \"{}\"".format(det[0]["class"]))
                    self.tracking = True
                    azi, elev = self.calculate_azimuth_elevation(det[0]["lat"], det[0]["lon"])
                    conf = int(det[0]["score"] * 255)
                    self.start = self.current_time_millis()
                    self.drone(follow_me.set_target_is_controller(0))
                    self.drone(follow_me.target_image_detection(azi, elev, 0.0, conf, 1, self.current_time_millis() - self.start))
                    self.drone(follow_me.target_framing_position(50, 50))
                    self.drone(follow_me.start(self.behavior, _no_expect=True))
                elif self.tracking and len(det) > 0:
                    print(f"Got detection from cloudlet: {json.dumps(det)}")
                    azi, elev = self.calculate_azimuth_elevation(det[0]["lat"], det[0]["lon"])
                    conf = int(det[0]["score"] * 255)
                    self.drone(follow_me.target_image_detection(azi, elev, 0.0, conf, 0, self.current_time_millis() - self.start))
                info = self.drone.get_state(follow_me.mode_info)
                state = self.drone.get_state(follow_me.target_image_detection_state)
                print(info)
                print(state)
            except Exception as e:
                print(f"Exception: {e}")
    
    def stop(self):
        self.context.destroy()
        self.active = False
        if self.tracking:
            self.drone(follow_me.stop())
            self.tracking = False
