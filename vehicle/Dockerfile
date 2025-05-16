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

COPY vehicle/requirements.txt requirements-1.txt
COPY vehicle/mission/requirements.txt requirements-2.txt

RUN pip install --no-cache-dir -r requirements-1.txt \
 && pip install --no-cache-dir -r requirements-2.txt \
 && pip install --no-cache-dir protobuf==5.29.4 \
 && pip install --no-cache-dir opencv-python==4.10.0.84 \
 && pip install --no-cache-dir numpy==1.26.4

COPY vehicle /vehicle
RUN rm /vehicle/mission/interface
COPY backend/server/steeleagle-dsl/python/interface /vehicle/mission/interface
COPY protocol /protocol

WORKDIR /vehicle/launch
