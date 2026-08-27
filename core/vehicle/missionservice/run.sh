#!/bin/sh
# Launched by core/util.BasePlugin with this directory as the working
# directory. install.sh must have already built ./missionservice.
exec ./missionservice "$@"
