# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
# SPDX-License-Identifier: GPL-2.0-only

FROM ubuntu:22.04

LABEL org.opencontainers.image.vendor="CMU Satyalab" \
      org.opencontainers.image.authors=satya-group@lists.andrew.cmu.edu

ARG DEBIAN_FRONTEND=noninteractive

# Install uv from the distroless container image
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/
WORKDIR /steeleagle

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy the project into the image
ADD . /steeleagle

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

EXPOSE 5555 9099
