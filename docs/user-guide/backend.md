---
layout: default
title: Backend Setup
parent: User Guide
nav_order: 3
has_children: false
permalink: docs/user-guide/backend
---
# Backend Setup
Ensure your server is publicly accessible over the Internet. Then, navigate to the root directory of the SteelEagle [repository](https://github.com/cmusatyalab/steel-eagle/tree/main) on your server and run `cd cnc`. Then run `docker build . -t cmusatyalab/steel-eagle:latest`. This will build a container for the SteelEagle backend.

Next, you will need to set up the OpenScout backend which is responsible for running compute engines like object detection. clone the OpenScout [repository](https://github.com/cmusatyalab/openscout) onto the server, navigate to its root directory, and run `git checkout steel-eagle` followed by `docker build . -t cmusatyalab/openscout:steel-eagle`.

Finally, navigate back to the SteelEagle root directory and run `cd cnc/server` followed by `docker-compose up -d`. This will start the backend in the background.

The full command list is as follows:
```
cd /path/to/steel-eagle/cnc
# Build the SteelEagle backend
docker build . -t cmusatyalab/steel-eagle:latest
git clone git@github.com:cmusatyalab/openscout.git
cd /path/to/openscout
# Checkout the SteelEagle branch of OpenScout
git checkout steel-eagle
# Build the OpenScout backend
docker build . -t cmusatyalab/openscout:steel-eagle
cd /path/to/steel-eagle/cnc/server
# Start the backend!
docker-compose up -d
```

Logs for the backend should be viewable by running `docker-compose logs -f <OPTIONAL_SERVICE_NAME>`. Ensure that you are seeing output from `docker-compose logs -f gabriel-server`. This should log any new clients or drones connecting to the backend.

If you would like to read more about backend customization or other logging features, see the complete backend guide [here]({{ site.baseurl }}{% link cnc.md %}). Now that the backend is running, it's time to set up the simulation environment for the Parrot ANAFI.
