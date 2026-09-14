"""
daemon/manager.py

Base manager class.
"""

import asyncio
from abc import ABC, abstractmethod


class Manager(ABC):
    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @abstractmethod
    async def start(self) -> dict:
        pass

    @abstractmethod
    async def stop(self) -> dict:
        pass

    @abstractmethod
    def entrypoint(self) -> str:
        pass

    # ------------------------------------------------------------------
    # Status & logs
    # ------------------------------------------------------------------
    @abstractmethod
    def status(self) -> dict:
        pass

    @abstractmethod
    def get_logs(self, tail: int = 100) -> list[str]:
        pass

    @abstractmethod
    def subscribe(self) -> asyncio.Queue:
        pass

    @abstractmethod
    def unsubscribe(self, q: asyncio.Queue) -> None:
        pass
