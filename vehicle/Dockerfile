# SPDX-FileCopyrightText: 2025 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

FROM python:3.10-bookworm
LABEL maintainer="Satyalab <satya-group@lists.andrew.cmu.edu>"

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    iputils-ping \
    vim \
    curl \
    libgl1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip install --upgrade pip

COPY vehicle/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir protobuf==5.29.4
RUN pip install --no-cache-dir opencv-python==4.10.0.82
RUN pip install --no-cache-dir numpy==1.26.4

COPY protocol /protocol
COPY vehicle /vehicle

WORKDIR /vehicle/launch
