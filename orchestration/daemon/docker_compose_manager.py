"""
daemon/docker_compose_manager.py
"""

import asyncio
import threading
from pathlib import Path

from python_on_whales import DockerClient


class DockerComposeManager:
    """
    Wraps a docker-compose.yaml file.
    """

    MAX_LOG_LINES = 500

    def __init__(self, name: str, compose_files: list[Path], environment: list[Path]):
        self.name = name
        self._compose_files = compose_files
        self._client = DockerClient(
            compose_files=compose_files, compose_env_files=environment
        )

        self._subscribers: list[asyncio.Queue] = []
        self._stream_thread: threading.Thread | None = None
        self._stream_stop = threading.Event()
        # Keep a reference to the running event loop so the stream thread
        # can safely schedule puts onto asyncio Queues.
        self._loop: asyncio.AbstractEventLoop | None = None

    def entrypoint(self) -> str:
        entrypoint = "docker compose "
        for f in self._compose_files:
            entrypoint += str(f)
        return entrypoint

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> dict:
        # Capture the running event loop at start time (called from an
        # async context via run_in_executor, so the loop is active).
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self._client.compose.up(pull="missing", detach=True)
        containers = self._client.compose.ps()
        return {
            "status": "started",
            "containers": [
                {"id": container.config.hostname, "status": container.state.status}
                for container in containers
            ],
        }

    def stop(self) -> dict:
        self._client.compose.down()
        containers = self._client.compose.ps()
        if len(containers) == 0:
            return {"status": "stopped"}
        else:
            return {
                "containers": [
                    {"id": container.config.hostname, "status": container.state.status}
                    for container in containers
                ]
            }

    # ------------------------------------------------------------------
    # Status & logs
    # ------------------------------------------------------------------

    def status(self) -> dict:
        containers = self._client.compose.ps()
        return {
            "containers": [
                {
                    "id": container.config.hostname,
                    "status": container.state.status,
                    "image": " ".join(
                        self._client.image.inspect(container.image).repo_tags
                    ),
                    "name": container.name,
                }
                for container in containers
            ]
        }

    def get_logs(self, tail: int = 100) -> list[str]:
        raw = self._client.compose.logs(tail=tail, timestamps=False)
        return [line for line in raw.splitlines() if line]

    def subscribe(self) -> asyncio.Queue:
        """Returns a Queue that receives new log lines from the container."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass
