import zmq
import time
from dataclasses import dataclass
from typing import Any
# Protocol import
import bindings.python.testing.testing_pb2 as test_proto
# Sequencer import
from message_sequencer import Topic

# Test request holder
@dataclass
class Request:
    method_name: str = None
    request: Any = None
    response: Any = None
    status: int = 2
    identity: str = 'server'

'''
Helper methods.
'''
async def wait_for_services(required, command_socket, timeout=5.0):
    # Wait for the necessary services to spin up
    start = time.time()
    while len(required) > 0 and time.time() - start < timeout:
        try:
            identity, ready = await command_socket.recv_multipart(flags=zmq.NOBLOCK)
            service = test_proto.ServiceReady()
            service.ParseFromString(ready)
            if service.readied_service in required:
                required.remove(service.readied_service)
        except zmq.error.Again:
            pass
        except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
            return
    if len(required):
        raise TimeoutError(f"Services did not report in!")

async def send_requests(requests, swarm_controller, mission):
    # Send messages and read the output
    output = []
    output.append((Topic.DRIVER_CONTROL_SERVICE, 'ConnectRequest'))
    for req in requests:
        identity = req.identity
        if identity == 'internal':
            assert(await mission.send_recv_command(req))
            output.append((Topic.MISSION_SERVICE, req.request.DESCRIPTOR.name))
            service = req.method_name.split('.')[0]
            if service == 'Control' and req.status == 2:
                output.append((Topic.DRIVER_CONTROL_SERVICE, req.request.DESCRIPTOR.name))
            output.append((Topic.MISSION_SERVICE, req.response.DESCRIPTOR.name))
        elif identity == 'external' or identity == 'server':
            assert(await swarm_controller.send_recv_command(req))
            output.append((Topic.SWARM_CONTROLLER, req.request.DESCRIPTOR.name))
            service = req.method_name.split('.')[0]
            output.append((Topic.DRIVER_CONTROL_SERVICE if service == 'Control' else Topic.MISSION_SERVICE, req.request.DESCRIPTOR.name))
            output.append((Topic.SWARM_CONTROLLER, req.response.DESCRIPTOR.name))
    return output

