# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
# SPDX-License-Identifier: GPL-2.0-only

# Built by backend/server/docker-compose.yml, which passes two more build
# contexts: Gabriel's repository as "gabriel-src", and steeleagle's api/python
# as "protocol". The image keeps the layout of a developer's checkout, so the
# path sources in pyproject.toml resolve, and Gabriel's binding finds
# libgabriel.so in its repository.

# libgabriel.so, for Gabriel's Python binding. Built on the same Debian as the
# image below, so its glibc matches.
FROM rust:1.98-bookworm AS libgabriel
# iceoryx2's bindings are generated with bindgen, which needs libclang.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libclang-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src/gabriel-rust
COPY --from=gabriel-src . .
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/gabriel-rust/target \
    cargo build --release --locked -p gabriel \
    && cp target/release/libgabriel.so /libgabriel.so

FROM debian:bookworm-slim

LABEL org.opencontainers.image.vendor="CMU Satyalab" \
      org.opencontainers.image.authors=satya-group@lists.andrew.cmu.edu

# Install uv from the distroless container image
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/

COPY --from=gabriel-src python /src/gabriel-rust/python
COPY --from=gabriel-src rust/include /src/gabriel-rust/rust/include
COPY --from=libgabriel /libgabriel.so /src/gabriel-rust/target/release/libgabriel.so
COPY --from=protocol . /src/steeleagle-go/api/python

WORKDIR /src/steeleagle-go/backend/server/engines/telemetry
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

ENTRYPOINT ["uv", "run", "telemetry.py"]
