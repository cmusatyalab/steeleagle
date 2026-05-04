import pytest
from fastapi.testclient import TestClient

from .main import app


@pytest.fixture(scope="session")
def client():
    # The 'with' statement here ensures startup/shutdown events run
    with TestClient(app) as c:
        yield c


@pytest.mark.backend
class TestBackend:
    def test_status_notstarted(self, client):
        response = client.get("/services/backend/status")
        assert response.status_code == 200
        assert response.json() == {"service": "gcs", "status": "not_started"}

    def test_start(self, client):
        response = client.post("/services/backend/start")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "started"

    def test_status_running(self, client):
        response = client.get("/services/backend/status")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "running"


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

    def test_install(self, client):
        response = client.post("/gcs/install")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "installed"

    def test_build(self, client):
        response = client.post("/gcs/build")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "build_successful"


def test_get_services(client):
    response = client.get("/services")
    assert response.status_code == 200
    assert len(response.json().get("services")) == 4  # gcs, vehicle, backend, sim
