# only for task developer

from . import VEHICLE, COMPUTE
from .datatypes.telemetry import DriverTelemetry
from .datatypes.result import FrameResult

async def fetch_results(topic) -> FrameResult:
    await COMPUTE.get_result(topic)

async def fetch_telemetry() -> DriverTelemetry:
    await VEHICLE.get_telemetry()

async def consume_last(async_iterable):
    """Consume an async iterator and return the last item (or None if empty)."""
    last = None
    async for item in async_iterable:
        last = item
    return last
