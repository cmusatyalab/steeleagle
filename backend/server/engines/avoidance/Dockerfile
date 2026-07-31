FROM nvidia/cuda:12.4.0-devel-ubuntu22.04

LABEL org.opencontainers.image.vendor="CMU Satyalab" \
      org.opencontainers.image.authors=satya-group@lists.andrew.cmu.edu

ARG DEBIAN_FRONTEND=noninteractive

# Install libgl1 so that no headless opencv doesn't complain
RUN apt update && apt-get install -y libgl1-mesa-glx libglib2.0-0 libglib2.0-dev

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
#ENTRYPOINT ["./entrypoint.sh"]
