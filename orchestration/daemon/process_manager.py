"""
daemon/process_manager.py

Manages a long-running Python (or any) subprocess.
Captures stdout/stderr into a rolling in-memory buffer and exposes
an asyncio.Queue per subscriber for real-time log streaming.
"""

import asyncio
import collections
from datetime import UTC, datetime


class ProcessManager:
    """
    Starts, stops, and monitors a subprocess. Captures all output into a
    rolling deque (default 500 lines) and fans it out to SSE subscribers
    via per-subscriber asyncio.Queues.
    """

    MAX_LOG_LINES = 500

    def __init__(self, name: str, command: list[str]):
        self.name = name
        self.command = command

        self._process: asyncio.subprocess.Process | None = None
        self._started_at: datetime | None = None
        self._log_buffer: collections.deque[str] = collections.deque(
            maxlen=self.MAX_LOG_LINES
        )
        self._subscribers: list[asyncio.Queue] = []
        self._reader_task: asyncio.Task | None = None

    def entrypoint(self) -> str:
        return " ".join(self.command)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, kwargs: list[str] | None = None) -> dict:
        if self._is_running():
            return {"status": "already_running", "pid": self._process.pid}

        self._process = await asyncio.create_subprocess_exec(
            *self.command + kwargs,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # merge stderr → stdout
        )
        self._started_at = datetime.now(UTC)

        # Background task drains stdout and fans out to subscribers.
        self._reader_task = asyncio.create_task(
            self._drain_output(), name=f"{self.name}-reader"
        )

        return {"status": "started", "pid": self._process.pid}

    async def stop(self) -> dict:
        if not self._is_running():
            return {"status": "not_running"}

        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except TimeoutError:
            self._process.kill()
            await self._process.wait()

        if self._reader_task:
            self._reader_task.cancel()

        return {"status": "stopped", "exit_code": self._process.returncode}

    # ------------------------------------------------------------------
    # Status & logs
    # ------------------------------------------------------------------

    def status(self) -> dict:
        if self._process is None:
            return {"status": "not_started"}
        if self._is_running():
            return {
                "status": "running",
                "pid": self._process.pid,
                "started_at": self._started_at.isoformat(),
            }
        return {
            "status": "exited",
            "exit_code": self._process.returncode,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }

    def get_logs(self, tail: int = 100) -> list[str]:
        """Return the last `tail` lines from the in-memory buffer."""
        buf = list(self._log_buffer)
        return buf[-tail:]

    def subscribe(self) -> asyncio.Queue:
        """
        Returns a Queue that will receive each new log line as it arrives.
        Call unsubscribe() when done.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def _drain_output(self) -> None:
        """Read lines from the child process and fan them out."""
        assert self._process and self._process.stdout
        try:
            async for raw in self._process.stdout:
                ts = datetime.now(UTC).strftime("%H:%M:%S")
                line = f"{raw.decode(errors='replace').rstrip()}"
                self._log_buffer.append(line)
                for q in list(self._subscribers):
                    try:
                        q.put_nowait(line)
                    except asyncio.QueueFull:
                        pass  # slow consumer — drop line rather than block
        except asyncio.CancelledError:
            pass
