# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import time

import olympe
from olympe.messages.gimbal import set_target

if __name__ == "__main__":
    drone = olympe.Drone("192.168.42.1")
    drone.connect()
    drone(
        set_target(
            gimbal_id=0,
            control_mode="position",
            yaw_frame_of_reference="none",
            yaw=0.0,
            pitch_frame_of_reference="absolute",
            pitch=30.0,
            roll_frame_of_reference="none",
            roll=0.0,
        )
    ).wait().success()
    time.sleep(10)
    drone.disconnect()
