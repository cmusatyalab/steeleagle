#!/bin/bash

CONFIG_PATH="${CONFIG_PATH:-../config.yaml}" PYTHONPATH=..:../../protocol python3 ../hub/__main__.py
