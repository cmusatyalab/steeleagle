#!/bin/bash

docker build -t cmusatyalab/steeleagle-detection-engine:v3.0-dev -f detection/Dockerfile detection
docker build -t cmusatyalab/steeleagle-avoidance-engine:v3.0-dev -f avoidance/Dockerfile avoidance
docker build -t cmusatyalab/steeleagle-telemetry-engine:v3.0-dev -f telemetry/Dockerfile telemetry
