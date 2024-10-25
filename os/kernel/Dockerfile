FROM --platform=linux/arm64/v8 alpine:latest
RUN apk add --no-cache python3 py3-pip
RUN apk add --no-cache py3-opencv

# Set python3 as the default python
RUN ln -sf python3 /usr/bin/python

# Install any required build dependencies
RUN apk add --no-cache gcc g++ bash musl-dev linux-headers

# Set the dir in the container
WORKDIR /steeleagle_os/kernel

RUN pip install --break-system-packages --no-deps --no-cache-dir gabriel-client==3.0

COPY ./os/kernel/requirements.txt /steeleagle_os/kernel/requirements.txt

# Install any required Python packages
RUN pip install --break-system-packages --no-cache-dir -r /steeleagle_os/kernel/requirements.txt

COPY ./os/kernel /steeleagle_os/kernel
COPY ./os/cnc_protocol /steeleagle_os/cnc_protocol
COPY ./os/util /steeleagle_os/util
