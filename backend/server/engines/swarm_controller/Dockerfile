# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

FROM ubuntu:20.04
LABEL Satyalab, satya-group@lists.andrew.cmu.edu

ARG DEBIAN_FRONTEND=noninteractive

# Install build and runtime dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    clinfo \
    curl \
    libgtk-3-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    python3 \
    python3-opencv \
    python3-pip \
    wget \
    # compiler requirement
    openjdk-17-jdk\
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#upgrade pip, otherwise tensorflow 1.15.0 will not be found
RUN pip3 install --upgrade pip

# Install Tensorflow and Gabriel's external dependencies
RUN python3 -m pip install --no-cache-dir \
    py-cpuinfo \
    'setuptools==41.0.0' \
    'websockets==8.0.0'

# You can speed up build slightly by reducing build context with
#     git archive --format=tgz HEAD | docker build -t cnc -
COPY backend/server/engines/swarm_controller/requirements.txt requirements.txt
RUN python3 -m pip install -r requirements.txt
COPY backend/server/engines/swarm_controller/swarm_controller.py swarm_controller.py
COPY protocol protocol
COPY vehicle/util util

EXPOSE 5555 9099
