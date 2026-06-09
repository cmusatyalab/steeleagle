import os
import threading
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc


def run():
    listen_addr = os.environ["LISTEN_SOCKET"]
    client_addr = os.environ["CLIENT_SOCKET"]

    class NotifyInterceptor(grpc.ServerInterceptor):
        def __init__(self):
            self.done = threading.Event()

        def intercept_service(self, continuation, handler_call_details):
            self.done.set()
            return continuation(handler_call_details)

    interceptor = NotifyInterceptor()
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        interceptors=[interceptor],
    )
    health_pb2_grpc.add_HealthServicer_to_server(health.HealthServicer(), server)
    server.add_insecure_port(f"unix://{listen_addr}")
    server.start()

    try:
        if not interceptor.done.wait(timeout=15.0):
            raise TimeoutError("expected rpc call, but none arrived")

        channel = grpc.insecure_channel(f"unix://{client_addr}")
        stub = health_pb2_grpc.HealthStub(channel)
        stub.Check(health_pb2.HealthCheckRequest())
        channel.close()
    finally:
        server.stop(grace=0)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"got the following error {e}")
        raise SystemExit(1)
