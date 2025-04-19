# Overview
SteelEagle is a software suite and edge orchestration system that transforms programmable commercial off-the-shelf (COTS) robotics platforms into fully-autonomous vehicles. By leveraging COTS economies of scale, SteelEagle can emulate the performance of expensive, onboard compute-based platforms on light, inexpensive hardware. 

The SteelEagle suite is equipped with a universal API which unifies disparate control SDKs under one programming scheme. This API is robot agnostic and can be used with any kind of programmable robotics hardware, including custom builds. Any drone that is SteelEagle API compatible can plug into the SteelEagle unified autonomy development stack which promotes code sharing and heterogeneous device collaboration. A visual mission scripting tool is also available to give non-programmers an easy way to interact with autonomous robots.

SteelEagle's edge processing pipelines allow drop-in drop-out configuration of AI backends, deployed in widely-used development environments instead of on embedded hardware. This makes SteelEagle an ideal testbed for AI robotics applications that need to quickly iterate and field deploy.

## Why Use SteelEagle?

### Low Cost
SteelEagle can be used with mass-market consumer robots which are extremely cost-optimized. This makes acquisition easier and cheaper than custom-built or niche products. It can also make swarm operations more economically feasible for constrained budgets.

### Accessibile
SteelEagle robots are designed to abstract away as much low-level control code as possible allowing users to focus on developing high-level tasks. Non-programmers can use the visual scripting API to design complex mission behavior without writing a single line of code. Programmers can use the Task Creator SDK to easily build out new functionality, and can use the Backend SDK to rapidly deploy new AI models across a robot fleet.

### Lightweight
Because SteelEagle robots rely on the edge for intelligence, they don't need to carry heavy onboard compute resources. This drives down weight, something which is particularly important for UAVs (unmanned aerial vehicles) due to [strict weight regulations](https://www.faa.gov/uas/commercial_operators/operations_over_people). SteelEagle enables autonomy on aircraft significantly smaller and lighter than traditional autonomous UAVs.

### Portable
SteelEagle is robot agnostic by design, able to accomodate any robot with a SDK. It supports heterogeneous collaborative robot swarms, and it gives users the ability to easily port code from one platform to another. While SteelEagle is unlikely to match the performance of purpose-built autonomous systems, its design allows for missions that pair such systems with smaller, cheaper helpers which can improve mission outcomes.

### BVLOS (Beyond Visual Line-of-Sight)
SteelEagle robots can communicate with an edge backend using any type of underlying radio communication, including LTE, without human supervision (beyond visual line-of-sight, or BVLOS for short). Operations like this are important for remote surveillance, especially in adversarial environments.

### Access to Powerful Compute
SteelEagle robots have access to much more powerful computation over the network than most mobile robots have onboard, due to their access to edge servers. Although edge servers are not as powerful as cloud servers, they are far more capable than any mobile computer and can deliver high-quality AI results with relatively low latency. 

## Drawbacks

### Limited Disconnected Operation
SteelEagle robots gain intelligence primarily through edge offload. Without a connection to the edge, they must rely on onboard hardware, which varies platform-to-platform. SteelEagle does support using available onboard compute either completely disconnected or partially disconnected from the edge in these cases.

### High Latency
For robots which have a highly latent connection to the edge, video and telemetry will also be latent. This may limit the effectiveness of backend AI algorithms. For this reason, edge offload is suboptimal for  latency-sensitive missions like high speed obstacle avoidance.

## Alternatives
Currently, the most popular robotic orchestration software is [ROS](https://www.ros.org/). ROS is a graph-based framework designed to abstract away hardware using a publisher-subscriber model. The strength of ROS is its modularity and its strong, dedicated community. However, it has a few design constraints. First, its underlying communication model is centered around a single robot rather than a robot swarm. This makes it suboptimal for use cases like multi-robot scenarios and remote video streaming, for example. To remedy these limitations, ROS must often rely on an external bridge node, such as this [swarm communication node](https://wiki.ros.org/swarm_ros_bridge). Second, ROS is cumbersome to work with and has a steep learning curve. For those inexperienced with robotics, this can significantly delay initial deployments.

SteelEagle can replace ROS, but it is also compatible with ROS. Depending on which functionality a user wants ROS to accomplish, SteelEagle can fill in the other parts of the autonomy stack. For more information, [read here]().

!!! note "UAV Users"
For users deploying on UAVs who want fine-grain control over the aircraft behavior at low latency, consider using [AirStack](https://docs.theairlab.org/main/docs/) another robotic autonomy framework developed at Carnegie Mellon University by [the AirLab](https://theairlab.org/).
