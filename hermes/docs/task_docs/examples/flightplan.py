# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

#/usr/bin/python3
import olympe
from olympe.messages.ardrone3.Piloting import TakeOff, Landing, moveTo
import olympe.enums.move as mode
from olympe.messages.ardrone3.PilotingState import SpeedChanged, GpsLocationChanged, FlyingStateChanged, moveToChanged

import threading
import requests
import math
import time

broadcasting = True

plan = [] 

plan.append({'lat': 40.415169, 'lng': -79.94897})

plan.append({'lat': 40.4157082, 'lng': -79.9492543})

plan.append({'lat': 40.4156265, 'lng': -79.9496244})

plan.append({'lat': 40.4153978, 'lng': -79.9495064})

plan.append({'lat': 40.4152548, 'lng': -79.9500375})

plan.append({'lat': 40.4149403, 'lng': -79.9499087})

plan.append({'lat': 40.415169, 'lng': -79.94897})


# Transponder thread which will update the drone's location on the map.
def transponder_thread(drone, tag):
    while (broadcasting):
        airspeed = 0
        try:
            speed = drone.get_state(SpeedChanged)
            airspeed = math.sqrt(speed["speedX"]**2 + speed["speedY"]**2 + speed["speedZ"]**2)
        except:
            pass
        try:
            loc = drone.get_state(GpsLocationChanged)
            state = drone.get_state(FlyingStateChanged)
            payload = {"data": {"tag": tag, "lat": loc["latitude"], "lng": loc["longitude"], "alt": loc["altitude"], "spd": airspeed, "state": state["state"].name, "plan": plan}, "droneid": tag}
            r = requests.post("http://transponder.pgh.cloudapp.azurelel.cs.cmu.edu:8080/update", json=payload)
            time.sleep(0.1)
        except Exception as e:
            # This means the data is not available just yet. Olympe will raise a runtime error if any of the
            # get_state() calls fail.
            print(e)
    # Delete the drone to cleanup.
    r = requests.post("http://transponder.pgh.cloudapp.azurelel.cs.cmu.edu:8080/delete", json={"droneid": tag})

if __name__ == "__main__":
        
    #eventually IP will be specified depending on what drone is chosen
    #IP = "192.168.42.1" #default anafi WiFi address
    IP = "10.202.0.1" #default virtual drone for Sphinx
    drone = olympe.Drone(IP)
    drone.connect()
    transponder = threading.Thread(target=transponder_thread, args=(drone, 'Anafi',))
    drone(TakeOff()).wait().success()
    transponder.start()
    
    drone(Landing()).wait().success()
    broadcasting = False
    transponder.join()
    drone.disconnect()