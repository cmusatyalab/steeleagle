# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
# SPDX-License-Identifier: GPL-2.0-only

FROM ubuntu:22.04

LABEL org.opencontainers.image.vendor="CMU Satyalab" \
      org.opencontainers.image.authors=satya-group@lists.andrew.cmu.edu

ARG DEBIAN_FRONTEND=noninteractive

# Install uv from the distroless container image
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/

# Install Python deps (make sure requirements.txt uses opencv-python or opencv-python-headless)
COPY pyproject.toml ./pyproject.toml

COPY telemetry.py telemetry.py
COPY telemetry_engine.py telemetry_engine.py

EXPOSE 5555 9099
