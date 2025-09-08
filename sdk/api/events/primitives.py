# _channel: Optional[grpc.aio.Channel] = None
# _stub: Optional[ctrl_rpc.ControlStub] = None

# async def get_stub() -> ctrl_rpc.ControlStub:
#     """Return a singleton ControlStub (creates the channel once)."""
#     global _channel, _stub
#     if _stub is None:
#         # Change to secure_channel(...) if you’re using TLS.
#         _channel = grpc.aio.insecure_channel("localhost:50051")
#         await _channel.channel_ready()
#         _stub = ctrl_rpc.ControlStub(_channel)  # NOTE: service “Control” -> ControlStub
#     return _stub

# tel = await context["data"].get_telemetry() # by telemetry handler