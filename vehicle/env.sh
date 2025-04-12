#!/bin/bash
# Simulation settings
export SIMULATION="True"
# General settings
export TAG="latest"
export PYTHONPATH="/home/xianglic/Documents/steeleagle/:/home/xianglic/Documents/steeleagle/vehicle/:/home/xianglic/Documents/steeleagle/protocol:$PYTHONPATH"
# Driver settings
export DRONE_ARGS='{"type": "SkyViper2450GPS", "id": "Viper", "connection_string": "udp:0.0.0.0:14550"}'
export DRIVER_ARGS='{}'
# Frame settings
export FFMPEG_THREADS="1"
export SAVE_FRAMES="false"
export STREAM_SIM_URL="http://127.0.0.1:5000/video_feed"
export STREAM_MINI_URL="http://192.168.99.1/ajax/video.mjpg"
# Kernel settings
export STEELEAGLE_GABRIEL_SERVER="vm039.elijah.cs.cmu.edu"
export STEELEAGLE_GABRIEL_PORT="9099"
# compute settings
export CPT_CONFIG="
computes:
  - compute_id: 'compute1'
    compute_class: 'GabrielCompute'
"
# Port settings
export TEL_PORT="5001"
export CAM_PORT="5002"
export HOST_CMD_FRONT_CMDR_PORT="1003"
export CMD_FRONT_CMDR_PORT="5003"
export CMD_FRONT_USR_PORT="5004"
export CMD_BACK_PORT="5005"
export MSN_PORT="5006"
export CPT_USR_PORT="5008"
# Address settings
export CMD_ENDPOINT="127.0.0.1"
export DATA_ENDPOINT="127.0.0.1"
# Logging settings
export LOG_LEVEL="INFO"
export LOG_TO_FILE="false"