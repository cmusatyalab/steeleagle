---
sidebar_position: 2
---

# Adding a Vehicle Driver

SteelEagle vehicle drivers are _wrappers_ over an existing robot control SDK, with the goal of providing a
unified abstraction layer that the rest of the system can understand and interact with. In practice, 
this means creating a middleware, represented in the system as a [gRPC server](https://grpc.io/docs/what-is-grpc/introduction/)
that translates the SteelEagle specification into vehicle-specific SDK commands.

By implementing this translation layer, many disparate robot control SDKs can be
abstracted away under a single interface. This is the foundational element of SteelEagle's hardware-agnostic
design. Any robot with an open SDK, within reason, can be integrated into the SteelEagle pipeline and 
controlled via the SteelEagle DSL. Adding a new vehicle driver to SteelEagle is a mostly straightforward process,
but a few caveats should be noted:
1. SteelEagle makes a _best effort_ attempt at compatibility. Because of how varied robot control schemes are,
it is likely not possible to build a perfectly unified control API. Even so, close-enough compatibility is still
good enough to do interesting things!
2. Many vehicles share autopilots with already existing vehicle drivers, so it may be easier to derive from
an existing driver rather than writing a new one from scratch.
3. SteelEagle is not concerned with _how_ a translation is achieved, so long as the abstraction
is maintained. This leaves the door open for all kinds of third-party integrations (e.g. [ROS]()).
4. Any parts of the specification that the vehicle cannot do can be safely left unimplemented. We understand
that not all vehicles can do everything! The DSL is designed to adapt to different vehicle abilities.

:::warning

Before adding a vehicle, it is highly recommended that you understand the SteelEagle [vehicle runtime architecture](/reference/runtime).

:::

## Requirements
To create a new vehicle driver in Python, first [install `steeleagle_sdk`](/sdk/python). You will need
it to access the native protocol bindings in the [`protocol` module](/sdk/python/steeleagle_sdk/protocol).

If using a different language than Python, you will need to generate the gRPC bindings in your language of choice.
You can learn about generating gRPC bindings [here](https://grpc.io/docs/languages/). In general, gRPC
supports most major languages including Python, C++, Java, and Go. Feel free to choose any gRPC compatible
language, especially if the robot interface SDK is designed for it! 
