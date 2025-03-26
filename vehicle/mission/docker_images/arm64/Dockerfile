FROM --platform=linux/arm64/v8 ubuntu:22.04

# Install Python 3.10, pip, and necessary build tools
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip \
    build-essential \
    bash \
    && ln -sf python3.10 /usr/bin/python

# Set the working directory
WORKDIR /steeleagle_os/user

# Copy necessary files into the container
COPY ./os/user /steeleagle_os/user
COPY ./os/cnc_protocol /steeleagle_os/cnc_protocol
COPY ./os/util /steeleagle_os/util

# Install required Python packages
RUN pip install -r /steeleagle_os/user/requirements.txt
