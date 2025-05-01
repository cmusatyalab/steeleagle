#!/bin/bash

CONFIG_PATH="${CONFIG_PATH:-../config.yaml}" PYTHONPATH=..:../../protocol:../drivers python3 ../drivers/multicopter/driver.py
