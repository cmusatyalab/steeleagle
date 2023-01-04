<!--
SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab

SPDX-License-Identifier: GPL-2.0-only
-->

# Command and Control Gabriel Server

## Description

The command and control server (CNC for short), is used to communicate with both drones in the field, and commanders who wish to remotely control those drones. CNC leverages [gabriel](http://github.com/cmusatyalab/gabriel) to manage client connections, send serialized data back and forth, and perform flow control. A gabriel server has one or more cognitive engines that perform paritcular tasks on some sensor data from clients. In the case of CNC, there is one newcognitive engines: cnc. The cnc engine is responsible for handing command and control messages from commanders and sending them to drones. It also is responsible for receiving the latest image frame each drone, and sending it to any connected commanders if they are viewing that drone.

Steel Eagle leverages [OpenScout](https://github.com/cmusatyalab/openscout) and its object detection and face recognition engines. It also utilizes the ELK containers that are part of OpenScout for later analysis.  In the future, we may also have more engines that are responsible for tasks such as face recognition or obstacle avoidance. 

## Prerequisites

Docker and docker-compose must be installed. NVIDIA CUDA drivers must also be present on the host.  This [gist](https://gist.github.com/teiszler/3bdf9c2629ae49f2058977db11b07dfd) (or something similar) can be used to install docker, docker-compose, and CUDA.

## Usage

### Build/Obtain Docker Images

OpenScout already has docker images build on Docker Hub, however we need to first build the steel-eagle image until we expose this repository publicly, at which point we can also publish the steel-eagle image on Docker Hub.

```sh
cd ~/steel-eagle/cnc/
docker build . -t cmusatyalab/steel-eagle:latest
docker pull cmusatyalab/openscout:latest
docker pull cmusatyalab/openface:latest
```

### Configure docker-compose environment

In the `/steel-eagle/cnc/server/` directory, there is a template.env file that can be used as an example docker-compose environment. Copy and then modify it to control things such as the confidence thresholds for the face and object engines, the initial DNN model to load, and the public URL for the webserver.

```sh
cd ~/steel-eagle/server/
cp template.env .env
#edit .env file as necessary
```

### Launch containers with docker-compose

To launch all the containers and interleave the output from each container in the terminal:

```sh
cd ~/steel-eagle/cnc/server
docker-compose up
```

If you wish to launch the containers in the background, you can pass the -d flag to docker compose. You can then use docker logs to inspect what is happening to individual containers.

```sh
cd ~/steel-eagle/cnc/server
docker-compose up -d
```

If you run the containers in the background, you can view the logs with the following command:

```sh
docker-compose logs -f 
```

### Elasticsearch preparation

Follow the [steps](https://github.com/cmusatyalab/openscout/blob/master/README.md#6-create-elasticsearch-index) outlined in the OpenScout documentation to prepare the Elasticsearch index template.
