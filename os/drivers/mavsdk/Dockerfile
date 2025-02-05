# Use the Python slim image as the base
FROM --platform=$BUILDPLATFORM python:3.10.14-slim

# Set environment variable to avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary build tools, dependencies, and OpenCV dependencies
RUN apt-get update && apt-get install -y \
    bash \
    vim \
    iputils-ping \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /steeleagle_os/mavsdk_driver

COPY ./os/drivers/mavsdk/requirements.txt .

# Install required Python packages
RUN pip install -r /steeleagle_os/mavsdk_driver/requirements.txt

# Copy necessary files into the container
COPY ./os/drivers/mavsdk /steeleagle_os/mavsdk_driver
COPY ./os/cnc_protocol /steeleagle_os/cnc_protocol
COPY ./os/util /steeleagle_os/util
