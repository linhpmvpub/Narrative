from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from engine.settings import Settings


def database(url: str | None = None) -> Engine:
    engine = create_engine(url or Settings.from_env().database_url)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine
