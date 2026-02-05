# SteelEagle TAK (Cursor on Target) Daemon

This package provides a daemon that subscribes to Redis telemetry streams from SteelEagle vehicles and republishes the data as Cursor on Target (CoT) messages using PyTAK.

## Usage

```bash
# From the backend/server/tak directory
uv run python -m steeleagle_tak.daemon

# Or install and run
pip install .
steeleagle-tak
```

## Configuration

The daemon can be configured via environment variables:

- `REDIS_HOST`: Redis server hostname (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_USERNAME`: Redis username (optional)
- `REDIS_PASSWORD`: Redis password (optional)
- `COT_URL`: CoT destination URL (default: tcp://localhost:8087)
- `COT_STALE`: CoT stale time in seconds (default: 120)
- `POLL_INTERVAL`: Telemetry poll interval in seconds (default: 1)

## Dependencies

- `pytak>=7.2.1`
- `redis>=4.0.0`
- `cryptography>=39.0.0`
- `aiohttp>=3.8.0`

## License

Apache-2.0
