"""Engine/session wiring for the tabular AML store (SQLAlchemy over SQLite).

Kept separate from :mod:`.service` so the facade depends on an injected sessionmaker
rather than constructing engines/sessions itself (Dependency Inversion).
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import TabularConfig
from .models import Base


def build_engine(config: TabularConfig) -> Engine:
    """Create the SQLAlchemy engine for ``config.db_url``.

    For SQLite, every new DBAPI connection is switched to ``journal_mode=WAL`` +
    ``synchronous=NORMAL``. The default (rollback journal + ``synchronous=FULL``) fsyncs
    the whole database file on every commit, which is fine for occasional writes but makes
    bulk ingestion of million-row files (see ``TabularSystem``) commit-bound rather than
    insert-bound. WAL commits append to a separate log file instead, which is both safe for
    a single-writer local dev DB and far cheaper per commit. No-op (silently ignored by
    SQLite) for ``sqlite:///:memory:``, used by the test suite.
    """
    connect_args = {"check_same_thread": False} if config.db_url.startswith("sqlite") else {}
    engine = create_engine(config.db_url, connect_args=connect_args)
    if config.db_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001 - SQLAlchemy event signature
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """Create the ``accounts``/``transactions`` tables if they don't already exist."""
    Base.metadata.create_all(engine)


def build_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    """Build a :class:`~sqlalchemy.orm.sessionmaker` bound to ``engine``."""
    return sessionmaker(bind=engine)
