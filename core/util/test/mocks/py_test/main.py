import os
import threading
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc


def run():
    listen_addr = os.environ["LISTEN_SOCKET"]
    client_addr = os.environ["CLIENT_SOCKET"]

    done = threading.Event()

    def notify_interceptor(continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return None

        orig = handler.unary_unary
        if orig is None:
            return handler

        def wrapped(request, context):
            done.set()
            return orig(request, context)

        return grpc.unary_unary_rpc_method_handler(
            wrapped,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        interceptors=[notify_interceptor],
    )
    health_pb2_grpc.add_HealthServicer_to_server(health.HealthServicer(), server)
    server.add_insecure_port(f"unix:{listen_addr}")
    server.start()

    try:
        if not done.wait(timeout=15.0):
            raise TimeoutError("expected rpc call, but none arrived")

        channel = grpc.insecure_channel(f"unix:{client_addr}")
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
