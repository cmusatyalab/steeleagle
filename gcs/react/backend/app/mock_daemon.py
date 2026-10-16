"""In-memory stand-in for an eagled instance on the revised protocol, used
for `mock://` daemon addresses until the eagled rework lands -- see
docs/superpowers/specs/2026-10-15-gcs-generic-plugins-design.md.

State is a config TOML string, exactly what get_configuration returns;
configure validates and replaces it whole, as eagled does. The mock also
serves logs, which the real protocol no longer carries (they are moving to
logdy). Nothing persists across GCS backend restarts."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app import daemon_config
from app.daemon_backend import DaemonError, LogRecord, LogSource, ServiceRef

_BACKLOG_LINES = 5


class MockDaemonBackend:
    def __init__(
        self,
        address: str,
        config_toml: str,
        *,
        configure_delay: float = 1.5,
        follow_interval: float = 2.0,
    ) -> None:
        self.address = address
        self._config = config_toml
        self._configure_delay = configure_delay
        self._follow_interval = follow_interval
        self._log_seq: dict[str, int] = {}
        # What the daemon was asked to do, for tests: "configure", "reset",
        # or ("restart", [ServiceRef, ...]).
        self.events: list = []

    def _doc(self):
        # A config the daemon holds that isn't TOML is the daemon's failure,
        # reported as a DaemonError like every other operation's.
        try:
            doc = daemon_config.parse(self._config)
        except daemon_config.ConfigError as e:
            raise DaemonError(f"daemon config is not valid TOML: {e.message}") from e
        try:
            daemon_config.validate(doc)
        except daemon_config.ConfigError as e:
            raise DaemonError(
                f"daemon config has an unexpected shape: {e.message}"
            ) from e
        return doc

    def _refs(self) -> list[ServiceRef]:
        return [
            ServiceRef(section["name"], category)
            for category, section in daemon_config.list_sections(self._doc())
        ]

    async def get_configuration(self) -> str:
        return self._config

    async def configure(self, config_toml: str) -> None:
        try:
            daemon_config.validate(daemon_config.parse(config_toml))
        except daemon_config.ConfigError as e:
            raise DaemonError(f"invalid config: {e.message}") from e
        # Configure restarts the daemon and everything it runs.
        await asyncio.sleep(self._configure_delay)
        self._config = config_toml
        self.events.append("configure")

    async def reset_configuration(self) -> None:
        self._config = ""
        self.events.append("reset")

    async def restart_services(self, refs: list[ServiceRef]) -> None:
        known = set(self._refs())
        for ref in refs:
            if ref not in known:
                raise DaemonError(f"no {ref.category} named {ref.name!r}")
        self.events.append(("restart", list(refs)))

    async def list_log_sources(self) -> list[LogSource]:
        # Named as eagled names them: a vehicle logs its driver and mission
        # processes separately.
        names = ["eagled"]
        for ref in self._refs():
            names += (
                [f"{ref.name}-driver", f"{ref.name}-mission"]
                if ref.category == "vehicle"
                else [ref.name]
            )
        return [
            LogSource(
                name=name,
                running=True,
                size_bytes=80 * self._log_seq.get(name, _BACKLOG_LINES),
            )
            for name in names
        ]

    def _record(self, source: str, seq: int) -> LogRecord:
        level = "warn" if seq % 5 == 0 else "info"
        return LogRecord(
            source=source,
            seq=seq,
            time=datetime.now(timezone.utc),
            level=level,
            text=f"{source}: mock heartbeat {seq}",
            dropped=0,
        )

    async def stream_logs(
        self, sources: list[str], tail: int, follow: bool, after_seq: dict[str, int]
    ) -> AsyncIterator[LogRecord]:
        names = sources or [s.name for s in await self.list_log_sources()]
        for name in names:
            last = self._log_seq.setdefault(name, _BACKLOG_LINES)
            for seq in range(max(1, last - tail + 1), last + 1):
                if tail and seq > after_seq.get(name, 0):
                    yield self._record(name, seq)
        index = 0
        while follow:
            await asyncio.sleep(self._follow_interval)
            name = names[index % len(names)]
            index += 1
            self._log_seq[name] = self._log_seq.get(name, _BACKLOG_LINES) + 1
            yield self._record(name, self._log_seq[name])
