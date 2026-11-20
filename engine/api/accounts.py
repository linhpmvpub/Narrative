"""Provisioned identities; no public registration or client-selected role/tenant."""

import argparse
import hashlib
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from engine.db import database
from engine.models.contracts import utc
from engine.models.schema_v4 import tokens, users, writes

bearer = HTTPBearer(auto_error=False)


def hashed(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    id: str
    tenant_id: str
    role: str


def principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if not credentials or len(credentials.credentials) > 512:
        raise HTTPException(401, "Authentication required")
    engine = database()
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(
                    select(users, tokens.c.expires_at, tokens.c.revoked)
                    .join(tokens)
                    .where(tokens.c.token_hash == hashed(credentials.credentials))
                )
                .mappings()
                .first()
            )
        if not row or row["revoked"] or utc(row["expires_at"]) <= datetime.now(UTC):
            raise HTTPException(401, "Authentication required")
        return Principal(row["id"], row["tenant_id"], row["role"])
    finally:
        engine.dispose()


def administrator(user: Annotated[Principal, Depends(principal)]) -> Principal:
    if user.role != "admin":
        raise HTTPException(403, "Operator role required")
    return user


def provision(engine, tenant_id: str, *, admin: bool = False) -> tuple[str, str]:
    if not tenant_id.strip() or len(tenant_id) > 100:
        raise ValueError("Tenant name required (max 100 characters)")
    user_id, token = str(uuid4()), secrets.token_urlsafe(32)
    with engine.begin() as conn:
        conn.execute(
            users.insert().values(
                id=user_id, tenant_id=tenant_id, role="admin" if admin else "member"
            )
        )
        conn.execute(
            tokens.insert().values(
                token_hash=hashed(token),
                user_id=user_id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                revoked=False,
            )
        )
    return user_id, token


@contextmanager
def transaction(engine, user_id):
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        conn.execute(select(users.c.id).where(users.c.id == user_id).with_for_update()).one()
        yield conn


def write(user, route, key, payload, action):
    """Ownership lock, mutation and retry response commit in one transaction."""
    import json

    if not key or not 1 <= len(key) <= 128:
        raise HTTPException(422, "Idempotency-Key required (1–128 characters)")
    identity = hashed(json.dumps([user.id, route, key]))
    request_hash = hashed(json.dumps(payload, sort_keys=True, default=str))
    engine = database()
    try:
        with transaction(engine, user.id) as conn:
            old = conn.execute(select(writes).where(writes.c.id == identity)).mappings().first()
            if old:
                if old["request_hash"] != request_hash:
                    raise HTTPException(409, "Idempotency key reused with different request")
                return old["response"]
            response = action(conn)
            conn.execute(
                writes.insert().values(
                    id=identity, user_id=user.id, request_hash=request_hash, response=response
                )
            )
            return response
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Provision a local account; tokens expire in 30 days"
    )
    parser.add_argument("--tenant", required=True)
    parser.add_argument(
        "--admin", action="store_true", help="Global operator, not tenant administrator"
    )
    args = parser.parse_args()
    engine = database()
    try:
        uid, token = provision(engine, args.tenant, admin=args.admin)
        print(f"User: {uid}\nBearer token (shown once): {token}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
