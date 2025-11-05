# only for task developer

async def fetch_results():
    pass

async def fetch_telemetry():
    pass

async def consume_last(async_iterable):
    """Consume an async iterator and return the last item (or None if empty)."""
    last = None
    async for item in async_iterable:
        last = item
    return last
