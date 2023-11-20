---
layout: default
title: Command and Control Server
nav_order: 3
has_children: false
permalink: docs/cnc
---
<!--
SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab

SPDX-License-Identifier: GPL-2.0-only
-->
# Command and Control Gabriel Server

## Description

The command and control server (CNC for short), is used to communicate with both drones in the field, and commanders who wish to remotely control those drones. CNC leverages [gabriel](http://github.com/cmusatyalab/gabriel) to manage client connections, send serialized data back and forth, and perform flow control. A gabriel server has one or more cognitive engines that perform paritcular tasks on some sensor data from clients. In the case of CNC, there is one new cognitive engine: cnc. The cnc engine is responsible for handing command and control messages from commanders and sending them to drones. It also is responsible for receiving the latest image frame each drone, and sending it to any connected commanders if they are viewing that drone.

Steel Eagle leverages [OpenScout](https://github.com/cmusatyalab/openscout) and its object detection and face recognition engines. Additionally, the steel-eagle branch of the openscout repository adds an additional obstacle avoidance engine. It also utilizes the ELK containers that are part of OpenScout for later analysis. 

## Prerequisites

Docker and docker-compose must be installed. NVIDIA CUDA drivers must also be present on the host.  This [gist](https://gist.github.com/teiszler/3bdf9c2629ae49f2058977db11b07dfd) (or something similar) can be used to install docker, docker-compose, and CUDA.

## Usage

### Build/Obtain Docker Images



```sh
git clone git@github.com:cmusatyalab/steel-eagle.git
cd ~/steel-eagle/cnc/
docker build . -t cmusatyalab/steel-eagle:latest
git clone git@github.com:cmusatyalab/openscout.git
cd ~/openscout/server
git checkout steel-eagle
docker build . -t cmusatyalab/openscout:steel-eagle
```

### Configure docker-compose environment

In the `/steel-eagle/cnc/server/` directory, there is a template.env file that can be used as an example docker-compose environment. Copy and then modify it to control things such as the confidence thresholds for the face and object engines, the initial DNN model to load, and the public URL for the webserver.

```sh
cd ~/steel-eagle/server/
cp template.env .env
#edit .env file as necessary
```
* _DRONE_TIMEOUT_ - This value is used to control when the cnc server decides to invalidate a previously connected drone. If the drone hasn't sent any updates for this number of seconds, it will be considered lost.
* _TAG_, _OPENSCOUT_TAG_ - These values should match the tags used to build the containers in the previous section (TAG=latest, OPENSCOUT_TAG=steel-eagle)
* _STORE_ - When this is '--store', all incoming images will be stored to a docker volume (openscout-vol). Additionally, the output from the object detection and obstacle avoidance engines will be stored in subdirectories ('detected' and 'moa' respectively).

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
If you wish to see a particular log, you can specify a particular service(s):

```sh
docker-compose logs -f command-engine,gabriel-server
```
### Elasticsearch preparation

Follow the [steps](https://github.com/cmusatyalab/openscout/blob/master/README.md#6-create-elasticsearch-index) outlined in the OpenScout documentation to prepare the Elasticsearch index template.
