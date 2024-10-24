#!/bin/bash
# Get the directory where this env.sh script is located, even if sourced
SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")

# Export PYTHONPATH as os/
export PYTHONPATH=$SCRIPT_DIR

# driver
export STEELEAGLE_DRIVER_ARGS='{}'
export STEELEAGLE_DRIVER_DRONE_ARGS='{"ip":"192.168.42.1", "ffmpeg": true}'


# usr

# kernel
export STEELEAGLE_GABRIEL_SERVER='128.2.213.139'
export STEELEAGLE_GABRIEL_PORT='9099'

# port
export TEL_PORT="5001"
export CAM_PORT="5002"
export CMD_FRONT_PORT="5003"
export CMD_BACK_PORT="5004"
export MSN_PORT="5005"
export LCE_PORT="5006"

# ADDR
# export LOCALHOST="127.0.0.1"
export CMD_ENDPOINT="127.0.0.1"
export RC_ENDPOINT="127.0.0.1"
