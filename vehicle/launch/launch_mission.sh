#!/bin/bash

CONFIG_PATH="${CONFIG_PATH:-../config.yaml}" PYTHONPATH=..:../../protocol:../mission python3 ../mission/core/__main__.py
