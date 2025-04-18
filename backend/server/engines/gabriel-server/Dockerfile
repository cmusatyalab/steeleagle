# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

FROM ubuntu:20.04
LABEL Satyalab, satya-group@lists.andrew.cmu.edu

ARG DEBIAN_FRONTEND=noninteractive

# Install build and runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip

RUN pip3 install --upgrade pip

COPY backend/server/engines/gabriel-server/requirements.txt ./requirements.txt
RUN python3 -m pip install -r requirements.txt
COPY backend/server/engines/gabriel-server/main.py main.py
COPY vehicle/util util

EXPOSE 5555 9099

ENTRYPOINT ["python3", "main.py"]
