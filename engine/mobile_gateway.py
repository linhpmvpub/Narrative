"""Read-only mobile gateway. Run on loopback behind an email-restricted HTTPS tunnel."""

import re
import time
from collections import defaultdict

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from engine.api.security import SecurityBoundary

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SecurityBoundary)
UPSTREAM = "http://127.0.0.1:8888"
GET_PATHS = {
    "/",
    "/map",
    "/news",
    "/api/v0/news",
    "/api/v0/news/sources",
    "/api/v0/news/clusters",
    "/label",
    "/api/v0/annotations/packets",
    "/healthz",
    "/readyz",
    "/api/v0/stocks",
    "/api/v0/narratives",
    "/api/v0/narratives/templates",
    "/api/v0/subscriptions",
    "/api/v0/impact-map",
    "/api/v0/impact-map/demo",
}
POST_PATHS = {
    "/api/v0/impact-map/scenario",
    "/api/v0/impact-map/demo-scenario",
    "/api/v0/development-feed/refresh",
}
buckets: dict = defaultdict(list)


def allowed(method, path):
    if method == "POST":
        return path in POST_PATHS or bool(
            re.fullmatch(r"/api/v0/annotations/[a-f0-9]{64}/cases/[a-f0-9]{64}/labels", path)
        )
    if method != "GET":
        return False
    return (
        path in GET_PATHS
        or bool(re.fullmatch(r"/api/v0/annotations/[a-f0-9]{64}/cases(?:/[a-f0-9]{64})?", path))
        or bool(re.fullmatch(r"/assets/[a-zA-Z0-9_.-]+", path))
        or bool(re.fullmatch(r"/api/v0/threads/[0-9a-fA-F-]{36}/(feed|story)", path))
    )


async def forward(method, path, query, headers, body):
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        return await client.request(
            method, UPSTREAM + path, params=query, headers=headers, content=body
        )


@app.get("/api/v0/client-capabilities")
def capabilities():
    return {"read_only": True, "remote_preview": True}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy(request: Request, path: str):
    path = "/" + path
    if not allowed(request.method, path):
        return JSONResponse(
            {"message": "Route unavailable on read-only mobile gateway"}, status_code=404
        )
    now = time.monotonic()
    identity = request.headers.get("cf-connecting-ip") or (
        request.client.host if request.client else "unknown"
    )
    if len(buckets) > 5000:
        for key in list(buckets):
            if not buckets[key] or buckets[key][-1] < now - 60:
                del buckets[key]
        if len(buckets) > 5000:
            return JSONResponse({"message": "Gateway busy"}, status_code=429)
    recent = [t for t in buckets[identity] if t > now - 60]
    if len(recent) >= 180:
        return JSONResponse({"message": "Request rate exceeded"}, status_code=429)
    buckets[identity] = recent + [now]
    headers = {
        k: request.headers[k]
        for k in ("authorization", "content-type", "idempotency-key")
        if k in request.headers
    }
    try:
        result = await forward(
            request.method, path, request.query_params.multi_items(), headers, await request.body()
        )
    except httpx.HTTPError:
        return JSONResponse({"message": "Local research server is unavailable"}, status_code=503)
    response_headers = {
        k: v
        for k, v in result.headers.items()
        if k.lower()
        in {
            "content-type",
            "content-security-policy",
            "cache-control",
            "referrer-policy",
            "x-content-type-options",
        }
    }
    return Response(result.content, status_code=result.status_code, headers=response_headers)
