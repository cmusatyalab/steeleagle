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

To compile a DSL mission, use the [`dsl`](../python/steeleagle_sdk/dsl) module within the [`steeleagle_sdk`](../python/) Python package or,
use the CLI utility packaged with `steeleagle_sdk`. Once `steeleagle_sdk` has been installed, run:
```bash
uv run compile_dsl YOUR_DSL_FILE
```

To compile from within Python:

```python
from steeleagle_sdk.dsl import build_mission
from dataclasses import asdict
import json

dsl_content = '' # DSL file content, loaded as a string.

# Build the mission.
mission_ir = build_mission(dsl_content)
print(json.dumps(asdict(mission_ir))) # Convert the mission IR to JSON.
```

## Running

If successful, the compiler will output a compiled `mission.json` file. This can then be sent to the vehicle using the [SteelEagle GCS](/reference/gcs) along with an optional KML file if the DSL contains KML references. The GCS workflow is recommended for most use-cases.

To upload a mission via script, use any gRPC compatible language and build gRPC bindings for the [SteelEagle protocol](/sdk/native). Or, use the [SteelEagle SDK](/sdk/python) with Python.
There are two ways to upload a mission from code:

<Tabs>
<TabItem value="server" label="Server Upload">
Sending via server requires a running [Swarm Controller](/reference/backend/swarm-controller) instance that is connected to the target vehicle(s).
This method allows users to easily deploy a mission to a swarm of vehicles by sending the same command with a different target vehicle.

First, [open a gRPC link to the server](/tutorial/first-flight). Then construct and send the following [`CommandRequests`](/sdk/python/steeleagle_sdk/protocol/services/remote_service_pb2#class-commandrequest):
```python
from steeleagle_sdk.protocol.services.remote_service_pb2 import CommandRequest
from steeleagle_sdk.protocol.services.mission_service_pb2 import UploadRequest, StartRequest
from steeleagle_sdk.protocol.rpc_helpers import generate_request

STUB = None # Stub connected to the Swarm Controller.
mission = '' # Mission json, loaded as a string.
kml = b'' # KML data for waypoint references, loaded as bytes (optional).
vehicle = '' # Name of the vehicle to send to.

def send_request(request):
    responses = []
    for response in STUB.Command(request):
        responses.append(response)
    return responses[-1].status == 2 # Check completion

request = CommandRequest()

upload = UploadRequest(request=generate_request())
upload.mission.content = mission
upload.mission.map = kml

request.Pack(upload)
request.method_name = "Mission.Upload"
request.vehicle_id = vehicle

assert(send_request(request))

start = StartRequest(request=generate_request())

request.Pack(upload)
request.sequence_number += 1
request.method_name = "Mission.Start"
request.vehicle_id = vehicle

assert(send_request(request))
```
</TabItem>    
<TabItem value="direct" label="Direct Upload">
Direct upload requires a running [vehicle](/reference/vehicle) instance that is accessible over the network, and is [configured for direct service access](/reference/vehicle/dsa#setup).
This method avoids setting up the SteelEagle backend and is thus a lightweight way to work with SteelEagle vehicles. This comes with a [few caveats](/reference/vehicle/dsa#caveats) which users should be aware of before flying.

First, [open a gRPC link to the vehicle](/reference/vehicle/dsa#setup). Then construct and send the following [`UploadRequest` and `StartRequest`](/sdk/python/steeleagle_sdk/protocol/services/mission_service_pb2):
```python
from steeleagle_sdk.protocol.services.mission_service_pb2 import UploadRequest, StartRequest
from steeleagle_sdk.protocol.rpc_helpers import generate_request

MISSION_STUB = None # Stub connected to vehicle kernel mission services.
mission = '' # Mission json, loaded as a string.
kml = b'' # KML data for waypoint references, loaded as bytes (optional).
vehicle = '' # Name of the vehicle to send to.

upload = UploadRequest(request=generate_request())
upload.mission.content = mission
upload.mission.map = kml
assert(MISSION_STUB.Upload(upload).status == 2)

start = StartRequest(request=generate_request())
assert(MISSION_STUB.Start(start).status == 2)
```
</TabItem>
</Tabs>

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
