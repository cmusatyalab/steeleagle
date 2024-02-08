---
layout: default
title: Backend Setup
parent: Quickstart
nav_order: 3
has_children: false
permalink: docs/quickstart/backend
---
# Backend Setup
Ensure your server is publicly accessible over the Internet. Then, navigate to the root directory of the SteelEagle [repository](https://github.com/cmusatyalab/steeleagle/tree/main) on your server and run `cd cnc`. Then run `docker pull cmusatyalab/steeleagle:latest`. This will fetch the container for the SteelEagle backend from Docker Hub.

Next, you will need to set pull the OpenScout backend which is responsible for running compute engines like object detection:  `docker pull cmusatyalab/openscout:steeleagle`.

Finally, navigate back to the SteelEagle root directory and run `cd cnc/server` followed by `docker compose up -d`. This will start the backend in the background.

The full command list is as follows:
```
cd /path/to/steeleagle/cnc
# Pull the SteelEagle backend
docker pull cmusatyalab/steeleagle:latest
# Pull the OpenScout backend
docker pull cmusatyalab/openscout:steeleagle
cd /path/to/steeleagle/cnc/server
# Copy env
cp template.env .env
# Create models dir and obtain YOLO model
mkdir models
cd models
wget https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5m.pt
# Start the backend!
cd ..
docker compose up -d
```

Logs for the backend should be viewable by running `docker compose logs -f <OPTIONAL_SERVICE_NAME>`. Ensure that you are seeing output from `docker compose logs -f gabriel-server`. This should log any new clients or drones connecting to the backend.

If you would like to read more about backend customization or other logging features, see the complete backend guide [here]({{ site.baseurl }}{% link modules/cnc.md %}). Now that the backend is running, it's time to set up the simulation environment for the Parrot ANAFI.
