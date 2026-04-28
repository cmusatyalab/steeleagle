"""
daemon/container_manager.py

Manages a single Docker container using the docker-py SDK.
Exposes the same start/stop/status/get_logs/subscribe surface as
ProcessManager so the daemon treats both types uniformly.

Threading note: docker-py's log streaming is synchronous/blocking, so we
run it in a background daemon thread and bridge back to asyncio using
loop.call_soon_threadsafe() to safely enqueue lines into asyncio.Queues
that live on the event loop thread.
"""

import asyncio
import threading
from typing import Any

import docker
import docker.errors
from docker.models.containers import Container


class ContainerManager:
    """
    Wraps a Docker container. The container is created fresh on first start
    and reused (restarted) on subsequent starts if it still exists.

    `run_kwargs` are forwarded directly to `client.containers.run()`, so
    anything docker-py supports (ports, env, volumes, networks, …) works.
    """

    MAX_LOG_LINES = 500

    def __init__(self, name: str, image: str, **run_kwargs: Any):
        self.name = name
        self.image = image
        self.run_kwargs = run_kwargs

        self._client = docker.from_env()
        self._subscribers: list[asyncio.Queue] = []
        self._stream_thread: threading.Thread | None = None
        self._stream_stop = threading.Event()
        # Keep a reference to the running event loop so the stream thread
        # can safely schedule puts onto asyncio Queues.
        self._loop: asyncio.AbstractEventLoop | None = None

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

        container = self._find()

        if container and container.status == "running":
            return {"status": "already_running", "id": container.short_id}

        if container:
            # Container exists but is stopped — just restart it.
            container.start()
            container.reload()
        else:
            # First time: pull image if missing, then create and run.
            self._ensure_image()
            container = self._client.containers.run(
                self.image,
                name=self.name,
                detach=True,
                **self.run_kwargs,
            )

        self._start_log_stream(container)
        return {"status": "started", "id": container.short_id}

    def stop(self) -> dict:
        container = self._find()
        if not container:
            return {"status": "not_found"}
        if container.status != "running":
            return {"status": "already_stopped", "id": container.short_id}

        self._stop_log_stream()
        container.stop(timeout=5)
        return {"status": "stopped", "id": container.short_id}

    # ------------------------------------------------------------------
    # Status & logs
    # ------------------------------------------------------------------

    def status(self) -> dict:
        container = self._find()
        if not container:
            return {"status": "not_found"}
        container.reload()
        return {
            "status": container.status,  # "running", "exited", etc.
            "id": container.short_id,
            "image": self.image,
            "name": self.name,
        }

    def get_logs(self, tail: int = 100) -> list[str]:
        container = self._find()
        if not container:
            return []
        raw = container.logs(tail=tail, timestamps=True).decode(errors="replace")
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find(self) -> Container | None:
        try:
            return self._client.containers.get(self.name)
        except docker.errors.NotFound:
            return None

    def _ensure_image(self) -> None:
        try:
            self._client.images.get(self.image)
        except docker.errors.ImageNotFound:
            print(f"[container_manager] Pulling image {self.image}…", flush=True)
            self._client.images.pull(self.image)

    def _fan_out(self, line: str) -> None:
        """Called from the stream thread; safely puts a line into every subscriber queue."""
        for q in list(self._subscribers):
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                pass  # slow consumer — drop rather than block

    def _start_log_stream(self, container: Container) -> None:
        """Spawn a daemon thread that follows container logs and fans them out."""
        self._stop_log_stream()
        self._stream_stop.clear()

        loop = self._loop  # captured on the event-loop thread

        def _stream() -> None:
            for raw in container.logs(stream=True, follow=True, timestamps=True):
                if self._stream_stop.is_set():
                    break
                line = raw.decode(errors="replace").rstrip()
                # Bridge back to the asyncio event loop thread safely.
                if loop and not loop.is_closed():
                    loop.call_soon_threadsafe(self._fan_out, line)

        self._stream_thread = threading.Thread(
            target=_stream, daemon=True, name=f"{self.name}-log-stream"
        )
        self._stream_thread.start()

    def _stop_log_stream(self) -> None:
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_stop.set()
            self._stream_thread.join(timeout=2)
