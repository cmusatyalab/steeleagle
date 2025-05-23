# Use the Python slim image as the base
FROM --platform=linux/arm64/v8 python:3.10.14-slim

# Set environment variable to avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary build tools, dependencies, and OpenCV dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libsqlite3-dev \
    libbz2-dev \
    zlib1g-dev \
    libncurses5-dev \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    # debugging purpose
    vim \
    # debugging purpose
    iputils-ping \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /steeleagle_os/driver_olympe

# Install required Python packages
COPY ./os/drivers/olympe/arm64/parrot_olympe-0.0.0-202410310237-py3-none-manylinux_2_31_aarch64.whl /steeleagle_os/driver_olympe/parrot_olympe-0.0.0-202410310237-py3-none-manylinux_2_31_aarch64.whl
RUN pip install --no-cache-dir /steeleagle_os/driver_olympe/parrot_olympe-0.0.0-202410310237-py3-none-manylinux_2_31_aarch64.whl

COPY ./os/drivers/olympe/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir --upgrade protobuf

# Copy necessary files into the container
COPY ./os/drivers/olympe /steeleagle_os/driver_olympe
COPY ./os/cnc_protocol /steeleagle_os/cnc_protocol
COPY ./os/util /steeleagle_os/util
