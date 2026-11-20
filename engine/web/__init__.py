"""Standalone static product shell; no browser persistence of bearer credentials."""

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).parent


def install(app):
    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(
            ROOT / "index.html",
            headers={
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'"
            },
        )

    @app.get("/assets/{name}", include_in_schema=False)
    def asset(name: str):
        if name not in {"app.js", "style.css", "demo.json"}:
            raise HTTPException(404, "Asset not found")
        return FileResponse(ROOT / name)
