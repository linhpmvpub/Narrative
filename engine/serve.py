"""Single-worker private service launcher with secret-file support and no access logs."""

import os
from pathlib import Path

import uvicorn

from engine.settings import Settings


def configure():
    path = os.getenv("DATABASE_URL_FILE")
    if path:
        if os.getenv("DATABASE_URL"):
            raise ValueError("Set DATABASE_URL or DATABASE_URL_FILE, not both")
        value = Path(path).read_text(encoding="utf-8").strip()
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("Deployment database secret must specify PostgreSQL")
        os.environ["DATABASE_URL"] = value
    Settings.from_env()


def main():
    configure()
    uvicorn.run(
        "engine.api:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        access_log=False,
        proxy_headers=False,
        limit_concurrency=32,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    main()
