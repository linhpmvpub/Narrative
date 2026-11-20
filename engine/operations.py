"""Single-process operator replay guard for the one-worker deployment."""

from contextlib import contextmanager
from threading import Lock

from fastapi import HTTPException

_replay_lock = Lock()


@contextmanager
def exclusive_replay():
    if not _replay_lock.acquire(blocking=False):
        raise HTTPException(409, "Another replay is running; retry after it completes")
    try:
        yield
    finally:
        _replay_lock.release()
