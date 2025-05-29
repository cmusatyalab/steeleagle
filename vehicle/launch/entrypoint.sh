#!/bin/bash

./launch_hub.sh &
./launch_driver.sh &
./launch_mission.sh &

wait
