---
sidebar_position: 1
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Writing DSL Missions

The SteelEagle DSL (Domain-Specific Language) is a custom language specification designed to simplify code for mobile robots.
It achieves this by using a finite state machine execution model, with composable actions and transition events.
By default, SteelEagle is configured to run compiled SteelEagle DSL files, though [this can be changed](mission/).

## Compiling

To compile a DSL mission, use the [`dsl`](../python/steeleagle_sdk/dsl) module within the [`steeleagle_sdk`](../python/) Python package. Once the
package has been installed, you can run:
```bash
uv run compile YOUR_DSL_FILE
```
To provide [custom actions or events](dsl/custom/), pass in the path to directory containing custom actions like so:
```bash
uv run compile YOUR_DSL_FILE --custom_defs /path/to/custom/defs
``` 

## Running

If successful, the compiler will output a compiled `mission.json` file. This can then be sent to the vehicle in one of two ways:
- Server: send a `Remote.Command` RPC with `method_name = "Mission.Upload"` to the swarm controller packed with an `UploadRequest` that has `mission.content` set to the `mission.json` string and `mission.map` set to a corresponding KML byte string (if applicable), then send a `Remote.Command` RPC with `method_name = "Mission.Start"` and a packed `StartRequest`
- Direct: send a `Mission.Upload` RPC to the vehicle kernel services endpoint with `UploadRequest.mission.content` set to the `mission.json` string and `UploadRequest.mission.map` set to a corresponding KML byte string (if applicable), then send a `Mission.Start` RPC

This should upload then start the mission.

:::danger

Running a `Mission.Start` RPC _will cause the vehicle to start moving_. Please make sure you and others are clear of the vehicle before sending this
command. For more information, see our [Safety Guide](/reference/safety).

:::

## Editor Tools

SteelEagle SDK comes with auto-complete tools for writing DSL files inside IDEs.

:::note

In future, a visual editor will be included that can build DSL scripts without any code!

:::
