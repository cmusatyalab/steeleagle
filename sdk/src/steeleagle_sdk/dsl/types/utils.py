# only for task developer

from .. import types
from .datatypes.result import FrameResult
from .datatypes.telemetry import DriverTelemetry


async def fetch_results(topic) -> FrameResult:
    return await types.COMPUTE.get_result(topic)


async def fetch_results_range(
    topic, t0: float, t1: float
) -> list[tuple[float, FrameResult]]:
    """Results recorded on `topic` in [t0, t1], oldest first. See Compute.get_results_range."""
    return await types.COMPUTE.get_results_range(topic, t0, t1)


async def fetch_telemetry() -> DriverTelemetry:
    return await types.VEHICLE.get_telemetry()


async def consume_last(async_iterable):
    """Consume an async iterator and return the last item (or None if empty)."""
    last = None
    async for item in async_iterable:
        last = item
    return last
