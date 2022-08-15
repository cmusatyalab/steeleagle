FROM ubuntu:18.04
LABEL Satyalab, satya-group@lists.andrew.cmu.edu

ARG DEBIAN_FRONTEND=noninteractive

# Install build and runtime dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    clinfo \
    curl \
    libgtk-3-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    python3 \
    python3-opencv \
    python3-pip \
    wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#upgrade pip, otherwise tensorflow 1.15.0 will not be found
RUN pip3 install --upgrade pip

# Install Tensorflow and Gabriel's external dependencies
RUN python3 -m pip install --no-cache-dir \
    protobuf \
    py-cpuinfo \
    pyzmq \
    'setuptools==41.0.0' \
    'websockets==8.0.0' \
    zmq 

# You can speed up build slightly by reducing build context with
#     git archive --format=tgz HEAD | docker build -t cnc -
COPY . cnc
WORKDIR cnc/server
RUN python3 -m pip install -r requirements.txt

EXPOSE 5555 9099
ENTRYPOINT ["./entrypoint.sh"]
