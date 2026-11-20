import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

log = logging.getLogger("focs.db")

DB_URL = settings.database_url
_is_sqlite = DB_URL.startswith("sqlite")
if _is_sqlite:
    # more connections than requests that can run at once (40 threads + 8 note writers): a frame never waits 30 s
    # for one and fails, as 25 students capturing at once did with the default 5 + 10
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False, "timeout": 30}, pool_pre_ping=True,
                           pool_size=20, max_overflow=40)
else:
    # Supabase's pooler (PgBouncer, port 6543) runs in transaction mode, which cannot keep
    # server-side prepared statements: psycopg must not create them (prepare_threshold=None).
    # A request waiting on the AI (5-30 s) keeps its connection: with 5 + 5, ten students asking at once would make
    # the next request fail after 30 s. The pooler takes up to 200 clients and queues them for its own few, so this
    # side keeps more than the requests that can run at once (40 threads + 8 note writers).
    # No pre-ping: it costs a round trip to the database on every request (150 ms when it is in another region).
    # Connections are renewed before the pooler would drop them, and TCP keepalives notice a dead one.
    engine = create_engine(DB_URL, connect_args={"prepare_threshold": None, "connect_timeout": 15, "keepalives": 1,
                                                 "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3},
                           pool_size=10, max_overflow=50, pool_recycle=240, pool_use_lifo=True)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")   # readers don't block the live-capture writer
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _default_sql(col) -> str:
    if col.server_default is None:
        return ""
    arg = col.server_default.arg
    if hasattr(arg, "text"):
        return f" DEFAULT {arg.text}"
    return " DEFAULT '{}'".format(str(arg).replace("'", "''"))


def _add_missing_columns() -> None:
    """Additive, idempotent schema sync: new model columns are added to existing tables.

    Keeps databases created by earlier Focs versions working without a migration step.
    Destructive changes (renames/drops) are intentionally not handled here.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in present:
                    continue
                ddl_type = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{_default_sql(col)}'))
                log.info("schema: added column %s.%s", table.name, col.name)


def init_db() -> None:
    from app import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
