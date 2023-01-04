# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import numpy as np
from geopy.distance import geodesic as GD

def calculate_azimuth_elevation(target_lat, target_lon, gps, alt):
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

if __name__ == "__main__":
    drone_gps = (40.442779, -79.938950, 10.0)
    target_gps = (40.442955, -79.939348)

    gps = {"latitude": drone_gps[0], "longitude": drone_gps[1]}
    alt = {"altitude": drone_gps[2]}

    azi, elev = calculate_azimuth_elevation(target_gps[0], target_gps[1], gps, alt)
    print("Azimuth: {0}, Elevation: {1}".format(azi * (180 / np.pi), elev * (180 / np.pi)))

