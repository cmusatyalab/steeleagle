"""
daemon/test_main.py

Expanded pytest suite for the orchestrator daemon API.

Each test class gets a fresh ``client`` fixture backed by lightweight fake
service implementations — no real subprocesses, Docker calls, or config files
are required.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import daemon.main as main_module

from .main import app
from .process_pool import ProcessPool

# ---------------------------------------------------------------------------
# Fake service implementations
# ---------------------------------------------------------------------------


class FakeProcessManager:
    """Drop-in stand-in for ProcessManager; tracks state in-memory."""

    def __init__(self, name: str, command: list[str]):
        self.name = name
        self.command = command
        self._state = "not_started"
        self._log_buffer: list[str] = []
        self._subscribers: list[asyncio.Queue] = []

    def entrypoint(self) -> str:
        return " ".join(self.command)

    async def start(self, kwargs: list[str] | None = None) -> dict:
        if self._state == "running":
            return {"status": "already_running", "pid": 99999}
        self._state = "running"
        return {"status": "started", "pid": 99999}

    async def stop(self) -> dict:
        if self._state != "running":
            return {"status": "not_running"}
        self._state = "stopped"
        return {"status": "stopped", "exit_code": 0}

    def status(self) -> dict:
        if self._state == "not_started":
            return {"status": "not_started"}
        if self._state == "running":
            return {
                "status": "running",
                "pid": 99999,
                "started_at": "2024-01-01T00:00:00+00:00",
            }
        return {"status": "exited", "exit_code": 0}

    def get_logs(self, tail: int = 100) -> list[str]:
        return list(self._log_buffer[-tail:])

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass


class FakeProcessPool(ProcessPool):
    """
    Inherits from the real ProcessPool so isinstance checks in main.py pass,
    but overrides start_instance to create FakeProcessManagers instead of
    spawning real subprocesses.
    """

    def __init__(self, name: str, command: list[str]):
        self.name = name
        self.command = command
        self._instances: dict[str, FakeProcessManager] = {}  # type: ignore[assignment]
        self._counter = 0

    async def start_instance(
        self, label: str | None = None, kwargs: list[str] | None = None
    ) -> dict:
        if label is None:
            self._counter += 1
            instance_id = f"{self.name}-{self._counter}"
        else:
            instance_id = label
        if kwargs is None:
            kwargs = []
        if instance_id not in self._instances:
            self._instances[instance_id] = FakeProcessManager(
                name=f"{self.name}.{instance_id}",
                command=self.command + kwargs,
            )
        result = await self._instances[instance_id].start(kwargs=[])
        return {"instance_id": instance_id, **result}


class FakeDockerComposeManager:
    """Lightweight stand-in for DockerComposeManager; no real Docker calls."""

    def __init__(self, name: str, compose_files: list, environment: list):
        self.name = name
        self._compose_files = compose_files
        self._state = "stopped"
        self._subscribers: list[asyncio.Queue] = []

    def entrypoint(self) -> str:
        return "docker compose (fake)"

    def start(self, kwargs: list[str] | None = None) -> dict:
        self._state = "running"
        return {
            "status": "started",
            "containers": [{"id": "abc123", "status": "running"}],
        }

    def stop(self) -> dict:
        self._state = "stopped"
        return {"status": "stopped"}

    def status(self) -> dict:
        return {
            "containers": [
                {
                    "id": "abc123",
                    "status": self._state,
                    "image": "test:latest",
                    "name": self.name,
                }
            ]
        }

    def get_logs(self, tail: int = 100) -> list[str]:
        return ["[INFO] fake container log line"]

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def list(self) -> dict:
        return {"services": {"web": {"image": "nginx:latest"}}}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_services() -> dict:
    return {
        "gcs": FakeProcessManager("gcs", ["uv", "run", "main.py"]),
        "sim": FakeProcessManager("sim", ["uv", "run", "simulator.py"]),
        "vehicle": FakeProcessPool("vehicle", ["uv", "run", "launch.py"]),
        "backend": FakeDockerComposeManager("backend", [], []),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def client():
    """
    Class-scoped TestClient with fake services injected via lifespan patching.
    Every test class gets a fresh set of fake services so state does not leak
    between classes.
    """
    main_module.SERVICES.clear()
    services = _make_services()
    with (
        patch("daemon.main.load_services", return_value=services),
        patch("daemon.main._get_roost_repo"),
        TestClient(app) as c,
    ):
        yield c
    main_module.SERVICES.clear()


@pytest.fixture
def fake_driver_repo(tmp_path: Path) -> MagicMock:
    """
    A mock git.Repo whose tree contains a single 'parrot' driver entry backed
    by a real (temporary) pyproject.toml so the route can open it.
    """
    driver_dir = tmp_path / "drivers" / "parrot"
    driver_dir.mkdir(parents=True)
    pyproject_path = driver_dir / "pyproject.toml"
    pyproject_path.write_text('[project]\ndescription = "Parrot ANAFI driver"\n')

    pyproject_item = MagicMock()
    pyproject_item.abspath = str(pyproject_path)

    driver_item = MagicMock()
    driver_item.type = "tree"
    driver_item.name = "parrot"
    driver_item.abspath = str(driver_dir)
    driver_item.__getitem__ = MagicMock(return_value=pyproject_item)

    def _drivers_getitem(key: str):
        if key == "parrot":
            return driver_item
        raise KeyError(key)

    drivers_tree = MagicMock()
    drivers_tree.__iter__ = MagicMock(return_value=iter([driver_item]))
    drivers_tree.__truediv__ = MagicMock(side_effect=_drivers_getitem)
    drivers_tree.__getitem__ = MagicMock(side_effect=_drivers_getitem)

    root_tree = MagicMock()
    root_tree.__getitem__ = MagicMock(return_value=drivers_tree)

    repo = MagicMock()
    repo.head.commit.tree = root_tree
    return repo


# ---------------------------------------------------------------------------
# Tests — services list
# ---------------------------------------------------------------------------


def test_get_services(client):
    response = client.get("/services")
    assert response.status_code == 200
    services = response.json().get("services", [])
    assert len(services) == 4  # gcs, sim, vehicle, backend
    names = {s["name"] for s in services}
    assert names == {"gcs", "sim", "vehicle", "backend"}


# ---------------------------------------------------------------------------
# Tests — process service lifecycle (using 'sim')
# ---------------------------------------------------------------------------


class TestSim:
    def test_status_not_started(self, client):
        response = client.get("/services/sim/status")
        assert response.status_code == 200
        assert response.json() == {"service": "sim", "status": "not_started"}

    def test_start(self, client):
        response = client.post("/services/sim/start")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "started"
        assert d["pid"] == 99999

    def test_status_running(self, client):
        response = client.get("/services/sim/status")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "running"

    def test_start_already_running(self, client):
        response = client.post("/services/sim/start")
        assert response.status_code == 200
        assert response.json()["status"] == "already_running"

    def test_stop(self, client):
        response = client.post("/services/sim/stop")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "stopped"
        assert d["exit_code"] == 0

    def test_status_after_stop(self, client):
        response = client.get("/services/sim/status")
        assert response.status_code == 200
        assert response.json()["status"] == "exited"

    def test_stop_when_not_running(self, client):
        response = client.post("/services/sim/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "not_running"


# ---------------------------------------------------------------------------
# Tests — GCS service + GCS-specific routes
# ---------------------------------------------------------------------------


@pytest.mark.gcs
class TestGCS:
    def test_status_notstarted(self, client):
        response = client.get("/services/gcs/status")
        assert response.status_code == 200
        assert response.json() == {"service": "gcs", "status": "not_started"}

    def test_start(self, client):
        response = client.post("/services/gcs/start")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "started"

    def test_status_running(self, client):
        response = client.get("/services/gcs/status")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "running"

    def test_stop(self, client):
        response = client.post("/services/gcs/stop")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "stopped"

    def test_install(self, client, monkeypatch):
        async def _fake_exec(cmd, use_shell: bool = False):
            return 0, b"nvm install log"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post("/gcs/install")
        assert response.status_code == 200
        assert response.json()["status"] == "installed"

    def test_install_failure(self, client, monkeypatch):
        async def _fake_exec(cmd, use_shell: bool = False):
            return 1, b"curl: command not found"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post("/gcs/install")
        assert response.status_code == 200
        assert response.json()["status"] == "installation_failed"

    def test_build(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(main_module.shutil, "which", lambda _: "/usr/bin/npm")
        monkeypatch.setattr(main_module, "_get_steeleagle_dir", lambda: tmp_path)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 0, b"webpack build log"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post("/gcs/build")
        assert response.status_code == 200
        assert response.json()["status"] == "build_successful"

    def test_build_npm_not_found(self, client, monkeypatch):
        monkeypatch.setattr(main_module.shutil, "which", lambda _: None)
        response = client.post("/gcs/build")
        assert response.status_code == 500
        assert "npm not found" in response.json()["detail"]

    def test_build_failure(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(main_module.shutil, "which", lambda _: "/usr/bin/npm")
        monkeypatch.setattr(main_module, "_get_steeleagle_dir", lambda: tmp_path)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 1, b"compilation error"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post("/gcs/build")
        assert response.status_code == 200
        assert response.json()["status"] == "build_failed"


# ---------------------------------------------------------------------------
# Tests — vehicle ProcessPool
# ---------------------------------------------------------------------------


class TestVehiclePool:
    def test_list_instances_initially_empty(self, client):
        response = client.get("/services/vehicle/pool")
        assert response.status_code == 200
        d = response.json()
        assert d["service"] == "vehicle"
        assert d["instances"] == []

    def test_start_instance_auto_id(self, client):
        response = client.post("/services/vehicle/pool")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "started"
        assert "instance_id" in d

    def test_list_instances_after_start(self, client):
        response = client.get("/services/vehicle/pool")
        assert response.status_code == 200
        instances = response.json()["instances"]
        assert len(instances) == 1
        assert instances[0]["status"] == "running"

    def test_start_instance_with_label(self, client):
        response = client.post(
            "/services/vehicle/pool", params={"label": "drone-alpha"}
        )
        assert response.status_code == 200
        d = response.json()
        assert d["instance_id"] == "drone-alpha"
        assert d["status"] == "started"

    def test_instance_status(self, client):
        response = client.get("/services/vehicle/pool/drone-alpha/status")
        assert response.status_code == 200
        d = response.json()
        assert d["instance_id"] == "drone-alpha"
        assert d["status"] == "running"

    def test_instance_logs(self, client):
        response = client.get("/services/vehicle/pool/drone-alpha/logs")
        assert response.status_code == 200
        d = response.json()
        assert "logs" in d
        assert isinstance(d["logs"], list)

    def test_stop_instance(self, client):
        response = client.post("/services/vehicle/pool/drone-alpha/stop")
        assert response.status_code == 200
        d = response.json()
        assert d["instance_id"] == "drone-alpha"
        assert d["status"] == "stopped"

    def test_list_after_stop(self, client):
        response = client.get("/services/vehicle/pool")
        assert response.status_code == 200
        instances = response.json()["instances"]
        # drone-alpha was stopped and removed; only the auto-id instance remains
        ids = [i["instance_id"] for i in instances]
        assert "drone-alpha" not in ids

    def test_stop_unknown_instance(self, client):
        response = client.post("/services/vehicle/pool/no-such-drone/stop")
        assert response.status_code == 404

    def test_status_unknown_instance(self, client):
        response = client.get("/services/vehicle/pool/no-such-drone/status")
        assert response.status_code == 404

    def test_logs_unknown_instance(self, client):
        response = client.get("/services/vehicle/pool/no-such-drone/logs")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — backend DockerCompose service
# ---------------------------------------------------------------------------


@pytest.mark.backend
class TestBackend:
    def test_status_notstarted(self, client):
        response = client.get("/services/backend/status")
        assert response.status_code == 200
        d = response.json()
        assert d["service"] == "backend"
        assert "containers" in d

    def test_start(self, client):
        response = client.post("/services/backend/start")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "started"

    def test_status_running(self, client):
        response = client.get("/services/backend/status")
        assert response.status_code == 200
        d = response.json()
        assert d["service"] == "backend"
        containers = d["containers"]
        assert len(containers) == 1
        assert containers[0]["status"] == "running"

    def test_stop(self, client):
        response = client.post("/services/backend/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"

    def test_backend_list(self, client):
        response = client.get("/backend/list")
        assert response.status_code == 200
        d = response.json()
        assert "services" in d


# ---------------------------------------------------------------------------
# Tests — service logs
# ---------------------------------------------------------------------------


class TestServiceLogs:
    def test_process_logs_initially_empty(self, client):
        response = client.get("/services/gcs/logs")
        assert response.status_code == 200
        d = response.json()
        assert d["service"] == "gcs"
        assert d["logs"] == []

    def test_process_logs_with_buffer(self, client):
        svc = main_module.SERVICES["gcs"]
        svc._log_buffer = ["line 1", "line 2", "line 3"]
        response = client.get("/services/gcs/logs")
        assert response.status_code == 200
        assert response.json()["logs"] == ["line 1", "line 2", "line 3"]
        svc._log_buffer = []

    def test_process_logs_tail(self, client):
        svc = main_module.SERVICES["gcs"]
        svc._log_buffer = [f"line {i}" for i in range(10)]
        response = client.get("/services/gcs/logs", params={"tail": 3})
        assert response.status_code == 200
        assert response.json()["logs"] == ["line 7", "line 8", "line 9"]
        svc._log_buffer = []

    def test_compose_logs(self, client):
        response = client.get("/services/backend/logs")
        assert response.status_code == 200
        d = response.json()
        assert d["service"] == "backend"
        assert isinstance(d["logs"], list)


# ---------------------------------------------------------------------------
# Tests — error cases
# ---------------------------------------------------------------------------


class TestServiceErrors:
    def test_unknown_service_status_404(self, client):
        response = client.get("/services/ghost/status")
        assert response.status_code == 404

    def test_unknown_service_start_404(self, client):
        response = client.post("/services/ghost/start")
        assert response.status_code == 404

    def test_unknown_service_stop_404(self, client):
        response = client.post("/services/ghost/stop")
        assert response.status_code == 404

    def test_unknown_service_logs_404(self, client):
        response = client.get("/services/ghost/logs")
        assert response.status_code == 404

    def test_pool_service_used_as_single_400(self, client):
        # vehicle is a ProcessPool; /services/vehicle/status expects a single service
        response = client.get("/services/vehicle/status")
        assert response.status_code == 400

    def test_pool_service_start_as_single_400(self, client):
        response = client.post("/services/vehicle/start")
        assert response.status_code == 400

    def test_single_service_used_as_pool_400(self, client):
        # gcs is a ProcessManager; /services/gcs/pool expects a pool
        response = client.get("/services/gcs/pool")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests — config endpoints
# ---------------------------------------------------------------------------


class TestConfigs:
    def test_list_configs(self, client):
        response = client.get("/configs")
        assert response.status_code == 200
        configs = response.json()["configs"]
        names = {c["name"] for c in configs}
        assert {"gcs", "backend", "vehicles", "simulator"} == names

    def test_inspect_unknown_config_404(self, client):
        response = client.post("/configs/no-such-config/inspect")
        assert response.status_code == 404

    def test_inspect_missing_file_404(self, client, monkeypatch, tmp_path):
        # Point the gcs config at a path that does not exist
        monkeypatch.setitem(main_module.CONFIGS, "gcs", tmp_path / "nonexistent.toml")
        response = client.post("/configs/gcs/inspect")
        assert response.status_code == 404

    def test_inspect_existing_config(self, client, monkeypatch, tmp_path):
        cfg_file = tmp_path / "gcs.toml"
        cfg_file.write_text('[server]\nhost = "localhost"\nport = 8080\n')
        monkeypatch.setitem(main_module.CONFIGS, "gcs", cfg_file)
        response = client.post("/configs/gcs/inspect")
        assert response.status_code == 200
        assert response.json()["server"]["host"] == "localhost"


# ---------------------------------------------------------------------------
# Tests — driver endpoints
# ---------------------------------------------------------------------------


class TestDrivers:
    def test_list_drivers_with_one_entry(self, client, fake_driver_repo, monkeypatch):
        monkeypatch.setattr(main_module, "_get_roost_repo", lambda: fake_driver_repo)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 0, b""

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.get("/drivers")
        assert response.status_code == 200
        drivers = response.json()["drivers"]
        assert len(drivers) == 1
        assert drivers[0]["name"] == "parrot"
        assert drivers[0]["desc"] == "Parrot ANAFI driver"
        assert drivers[0]["status"] == "installed"

    def test_list_drivers_shows_uninstalled(
        self, client, fake_driver_repo, monkeypatch
    ):
        monkeypatch.setattr(main_module, "_get_roost_repo", lambda: fake_driver_repo)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 1, b"uv sync check failed"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.get("/drivers")
        assert response.status_code == 200
        assert response.json()["drivers"][0]["status"] == "uninstalled/outdated"

    def test_install_driver_success(self, client, fake_driver_repo, monkeypatch):
        monkeypatch.setattr(main_module, "_get_roost_repo", lambda: fake_driver_repo)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 0, b"installed"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post("/drivers/parrot/install")
        assert response.status_code == 200
        d = response.json()
        assert d["driver"] == "parrot"
        assert d["result"] == "installed"

    def test_install_driver_not_found(self, client, fake_driver_repo, monkeypatch):
        monkeypatch.setattr(main_module, "_get_roost_repo", lambda: fake_driver_repo)
        response = client.post("/drivers/no-such-driver/install")
        assert response.status_code == 404

    def test_install_driver_failure(self, client, fake_driver_repo, monkeypatch):
        monkeypatch.setattr(main_module, "_get_roost_repo", lambda: fake_driver_repo)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 1, b"dependency resolution failed"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post("/drivers/parrot/install")
        assert response.status_code == 200
        assert response.json()["result"] == "installation_failed"


# ---------------------------------------------------------------------------
# Tests — DSL compile endpoint
# ---------------------------------------------------------------------------


class TestDSL:
    def test_compile_success(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(main_module, "_get_steeleagle_dir", lambda: tmp_path)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 0, b"Compiled successfully"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post(
            "/dsl/compile", params={"dsl_file": "mission.dsl", "output": "out.json"}
        )
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "compiled"
        assert d["output"] == "out.json"

    def test_compile_failure(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(main_module, "_get_steeleagle_dir", lambda: tmp_path)

        async def _fake_exec(cmd, use_shell: bool = False):
            return 1, b"SyntaxError: unexpected token"

        monkeypatch.setattr(main_module, "_execute_async_subprocess", _fake_exec)
        response = client.post("/dsl/compile", params={"dsl_file": "bad.dsl"})
        assert response.status_code == 200
        assert response.json()["status"] == "compilation_failed"
        assert "SyntaxError" in response.json()["log"]
