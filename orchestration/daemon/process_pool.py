"""
daemon/process_pool.py

Manages a dynamic collection of ProcessManager instances — one per running
(or previously-run) process. Instances are identified by a string ID that
is either auto-assigned ("1", "2", …) or supplied by the caller.
"""

import asyncio

from .process_manager import ProcessManager


class ProcessPool:
    """
    A named pool of ProcessManager instances.

    Each call to start_instance() either creates a new instance (with an
    auto-assigned or caller-supplied label) or restarts an existing stopped
    one if the same label is reused.
    """

    def __init__(self, name: str, command: list[str]):
        self.name = name
        self.command = command
        self._instances: dict[str, ProcessManager] = {}
        self._counter = 0

    def entrypoint(self) -> str:
        return " ".join(self.command)

    # ------------------------------------------------------------------
    # Instance lifecycle
    # ------------------------------------------------------------------

    async def start_instance(self, label: str | None = None) -> dict:
        """
        Start a new instance.  If `label` is given and an instance with that
        label already exists (even if stopped), it is restarted rather than
        duplicated.  Returns the instance_id alongside the start result.
        """
        if label is None:
            self._counter += 1
            instance_id = f"{self.name}-{str(self._counter)}"
        else:
            instance_id = label

        if instance_id not in self._instances:
            self._instances[instance_id] = ProcessManager(
                name=f"{self.name}.{instance_id}",
                command=self.command,
            )

        result = await self._instances[instance_id].start()
        return {"instance_id": instance_id, **result}

    async def stop_instance(self, instance_id: str) -> dict:
        mgr = self._get(instance_id)
        result = await mgr.stop()
        return {"instance_id": instance_id, **result}

    async def stop_all(self) -> list[dict]:
        return [
            await self.stop_instance(iid)
            for iid, mgr in self._instances.items()
            if mgr.status().get("status") == "running"
        ]

    # ------------------------------------------------------------------
    # Status & logs — delegate to the individual ProcessManager
    # ------------------------------------------------------------------

    def instance_status(self, instance_id: str) -> dict:
        mgr = self._get(instance_id)
        return {"instance_id": instance_id, **mgr.status()}

    def list_instances(self) -> list[dict]:
        return [
            {"instance_id": iid, **mgr.status()} for iid, mgr in self._instances.items()
        ]

    def get_logs(self, instance_id: str, tail: int = 100) -> list[str]:
        return self._get(instance_id).get_logs(tail=tail)

    def subscribe(self, instance_id: str) -> asyncio.Queue:
        return self._get(instance_id).subscribe()

    def unsubscribe(self, instance_id: str, q: asyncio.Queue) -> None:
        self._get(instance_id).unsubscribe(q)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get(self, instance_id: str) -> ProcessManager:
        mgr = self._instances.get(instance_id)
        if mgr is None:
            raise KeyError(f"No instance '{instance_id}' in pool '{self.name}'")
        return mgr
