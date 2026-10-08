import socket

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import presence_routes
from app.presence_routes import PresenceRegistry, resolve_host


@pytest.fixture
def client(monkeypatch):
    # A fresh registry per test, and no real DNS: TestClient's peer address is
    # the literal string "testclient".
    monkeypatch.setattr(presence_routes, "registry", PresenceRegistry())
    monkeypatch.setattr(presence_routes, "resolve_host", lambda ip: f"{ip}.example")
    app = FastAPI()
    app.include_router(presence_routes.router)
    return TestClient(app)


def test_first_viewer_is_told_it_is_the_only_one(client):
    with client.websocket_connect("/ws/presence") as ws:
        msg = ws.receive_json()

    assert len(msg["viewers"]) == 1
    viewer = msg["viewers"][0]
    assert viewer["ip"] == "testclient"
    assert viewer["host"] == "testclient.example"
    assert msg["you"] == viewer["id"]


def test_existing_viewer_is_notified_when_another_joins(client):
    with client.websocket_connect("/ws/presence") as first:
        first.receive_json()
        with client.websocket_connect("/ws/presence") as second:
            seen_by_first = first.receive_json()
            seen_by_second = second.receive_json()

    assert len(seen_by_first["viewers"]) == 2
    assert seen_by_first["viewers"] == seen_by_second["viewers"]
    assert seen_by_first["you"] != seen_by_second["you"]


def test_remaining_viewer_is_notified_when_another_leaves(client):
    with client.websocket_connect("/ws/presence") as first:
        first.receive_json()
        with client.websocket_connect("/ws/presence") as second:
            first.receive_json()
            second.receive_json()
        after_leave = first.receive_json()

    assert [v["id"] for v in after_leave["viewers"]] == [after_leave["you"]]


def test_resolve_host_returns_the_reverse_dns_name(monkeypatch):
    monkeypatch.setattr(
        socket, "gethostbyaddr", lambda ip: ("cassowary.example", [], [ip])
    )

    assert resolve_host("10.0.0.5") == "cassowary.example"


def test_resolve_host_falls_back_to_the_ip_when_lookup_fails(monkeypatch):
    def fail(ip):
        raise socket.herror("no PTR record")

    monkeypatch.setattr(socket, "gethostbyaddr", fail)

    assert resolve_host("10.0.0.6") == "10.0.0.6"


async def test_slow_lookup_does_not_hold_up_a_join(monkeypatch):
    import time

    monkeypatch.setattr(presence_routes, "RESOLVE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(presence_routes, "resolve_host", lambda ip: time.sleep(0.5))

    assert await presence_routes.lookup_host("10.0.0.7") == "10.0.0.7"
