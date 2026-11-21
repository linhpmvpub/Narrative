import secrets
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from engine.api.security import SecurityBoundary
from engine.db import database
from engine.models.schema_v1 import metadata
from engine.settings import Settings

app = FastAPI(
    title="Relationship & Impact Engine",
    version="0.1.0",
    description="P4 private product API. Identity verification pending. No live delivery.",
)
bearer = HTTPBearer(auto_error=False)
app.add_middleware(SecurityBoundary)


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    token = Settings.from_env().api_token
    if (
        not token
        or credentials is None
        or len(credentials.credentials) > 512
        or not secrets.compare_digest(credentials.credentials.encode(), token.encode())
    ):
        from engine.api.accounts import principal

        principal(credentials)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "request_id": str(uuid4()),
        },
    )


@app.get("/healthz")
def health() -> dict:
    Settings.from_env()
    return {"status": "ok", "phase": "P4", "delivery": "disabled"}


@app.get("/readyz")
def ready():
    engine = database()
    try:
        with engine.connect() as conn:
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if revision != "0006":
                raise HTTPException(503, "Database migration required")
        return {"status": "ready", "schema": revision}
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable or migration required") from None
    finally:
        engine.dispose()


def catalog(table_name: str, predicate=None) -> list[dict]:
    table = metadata.tables[table_name]
    query = select(table).order_by(table.c.id)
    if predicate is not None:
        query = query.where(predicate)
    engine = database()
    try:
        with engine.connect() as conn:
            return [dict(row) for row in conn.execute(query).mappings()]
    finally:
        engine.dispose()


@app.get("/api/v0/stocks", dependencies=[Depends(authenticate)])
def stocks() -> dict:
    return {
        "items": catalog(
            "rie_entities", metadata.tables["rie_entities"].c.entity_type == "company"
        ),
        "identity_verification": "pending",
    }


@app.get("/api/v0/narratives/templates", dependencies=[Depends(authenticate)])
def templates() -> dict:
    templates = metadata.tables["rie_narratives"]
    versions = metadata.tables["rie_narrative_versions"]
    return {
        "items": catalog(
            "rie_narrative_versions",
            versions.c.narrative_id.in_(
                select(templates.c.id).where(templates.c.is_template.is_(True))
            ),
        ),
        "activation": "requires_review",
    }


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "request_id": str(uuid4()),
            "fields": [list(e["loc"]) for e in exc.errors()],
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    status = 409 if isinstance(exc, IntegrityError) else 503
    return JSONResponse(
        status_code=status,
        content={
            "code": f"HTTP_{status}",
            "message": "Write conflict"
            if status == 409
            else "Database unavailable or migration required",
            "request_id": str(uuid4()),
        },
    )


# Import after app/auth definitions; storybook adds routes to the same product router.
from engine.api.product import router  # noqa: E402
from engine.storybook import product as storybook_routes  # noqa: E402, F401

app.include_router(router)

from engine.api.sec_ingestion import router as ingestion_router  # noqa: E402
from engine.api.sec_review import router as sec_router  # noqa: E402
from engine.web import install as install_web  # noqa: E402

app.include_router(sec_router)
app.include_router(ingestion_router)
install_web(app)
