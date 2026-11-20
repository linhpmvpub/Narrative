import os
import socket
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from engine.db import database
from engine.seed import seed

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    # PostgreSQL CI uses localhost. All other socket connections are rejected.
    original = socket.socket.connect

    def guarded(sock, address):
        if isinstance(address, tuple) and address[0] not in ("localhost", "127.0.0.1", "::1"):
            raise AssertionError("External network prohibited in offline tests")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    monkeypatch.setenv("LLM_MODE", "none")
    monkeypatch.setenv("SEND_NOTIFICATIONS", "false")
    monkeypatch.setenv("ALLOW_SYNTHETIC_LIVE", "false")


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    engine = database(url)
    seed(engine, ROOT / "config")
    yield engine
    engine.dispose()
    command.downgrade(config, "base")
