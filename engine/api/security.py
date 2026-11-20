"""Transport-independent API limits; deployment still needs TLS/rate/time limits."""

from uuid import uuid4

from starlette.responses import JSONResponse

MAX_BODY_BYTES = 65_536


class SecurityBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def protected_send(message):
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower()
                    not in (b"cache-control", b"referrer-policy", b"x-content-type-options")
                ]
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        async def reject(status, message):
            response = JSONResponse(
                status_code=status,
                content={"code": f"HTTP_{status}", "message": message, "request_id": str(uuid4())},
            )
            await response(scope, receive, protected_send)

        lengths = [v for k, v in scope["headers"] if k.lower() == b"content-length"]
        if lengths:
            try:
                if len(lengths) != 1 or not lengths[0].isdigit():
                    raise ValueError()
                length = int(lengths[0])
            except ValueError:
                await reject(400, "Invalid Content-Length")
                return
            if length > MAX_BODY_BYTES:
                await reject(413, "Request body exceeds 64 KiB")
                return
        # Enforce the decoded ASGI stream length even without Content-Length.
        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > MAX_BODY_BYTES:
                await reject(413, "Request body exceeds 64 KiB")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        if lengths and total != length:
            await reject(400, "Content-Length does not match request body")
            return
        delivered = False

        async def buffered_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, protected_send)
