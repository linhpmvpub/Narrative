"""Standalone static product shell; no browser persistence of bearer credentials."""

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).parent


def install(app):
    @app.get("/", include_in_schema=False)
    def home():
        return shell("index.html")

    @app.get("/review", include_in_schema=False)
    def review():
        return shell("review.html")

    @app.get("/news-review", include_in_schema=False)
    def news_review():
        return shell("news-review.html")

    @app.get("/news", include_in_schema=False)
    def news():
        return shell("news.html")

    @app.get("/map", include_in_schema=False)
    def impact_map():
        return shell("map.html")

    @app.get("/label", include_in_schema=False)
    def label():
        return shell("label.html")

    @app.get("/adjudicate", include_in_schema=False)
    def adjudicate():
        return shell("adjudicate.html")

    def shell(name):
        return FileResponse(
            ROOT / name,
            headers={
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'"
            },
        )

    @app.get("/assets/{name}", include_in_schema=False)
    def asset(name: str):
        if name not in {
            "app.js",
            "news.js",
            "news-review.js",
            "news.css",
            "style.css",
            "demo.json",
            "review.js",
            "review.css",
            "map.js",
            "map.css",
            "map-demo.json",
            "adjudicate.js",
            "adjudicate.css",
            "label.js",
            "label.css",
        }:
            raise HTTPException(404, "Asset not found")
        return FileResponse(ROOT / name)
