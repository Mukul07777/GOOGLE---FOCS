"""One-time copy of the local SQLite database into a new (empty) Postgres database, e.g. Supabase.

Runs automatically on startup when Focs points at Postgres, the Postgres database has no users yet
and a local focs.db exists. The copy is a single transaction (all or nothing) and the SQLite file is
never modified, so it remains a backup.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, func, inspect, select, text

from app.core.database import Base

log = logging.getLogger("focs.db")
CHUNK = 500


def copy_database(src_url: str, dst: Engine) -> dict[str, int]:
    """Copy every model table from ``src_url`` into ``dst`` (which must have no users).

    Rows are read through the model columns, so SQLite's text dates / 0-1 booleans come back as
    proper Python values. SQLite never enforced foreign keys; rows pointing at missing parents
    get the link cleared (nullable) or are skipped (required), because Postgres enforces them.
    """
    from app import models  # noqa: F401  (register tables)

    src = create_engine(src_url)
    src_tables = set(inspect(src).get_table_names())
    users = Base.metadata.tables["users"]
    counts: dict[str, int] = {}
    with src.connect() as s, dst.begin() as d:
        if d.execute(select(func.count()).select_from(users)).scalar():
            log.info("migration skipped: destination already has users")
            return {}
        present: dict[str, set] = {}
        for table in Base.metadata.sorted_tables:  # parents before children
            if table.name not in src_tables:
                continue
            src_cols = {c["name"] for c in inspect(src).get_columns(table.name)}
            cols = [c for c in table.columns if c.name in src_cols]
            rows = [dict(r._mapping) for r in s.execute(select(*cols))]
            kept, skipped = [], 0
            for row in rows:
                ok = True
                for col in cols:
                    for fk in col.foreign_keys:
                        value = row.get(col.name)
                        if value is not None and value not in present.get(fk.column.table.name, set()):
                            if col.nullable:
                                row[col.name] = None
                            else:
                                ok = False
                if ok:
                    kept.append(row)
                else:
                    skipped += 1
            for i in range(0, len(kept), CHUNK):
                d.execute(table.insert(), kept[i:i + CHUNK])
            present[table.name] = {r["id"] for r in kept if "id" in r}
            counts[table.name] = len(kept)
            if skipped:
                log.info("migration: %s skipped %d orphaned rows", table.name, skipped)
        if dst.dialect.name == "postgresql":
            # rows were inserted with explicit ids: move each id sequence past the copied data
            for table in Base.metadata.sorted_tables:
                if "id" in table.columns and counts.get(table.name):
                    d.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('\"{table.name}\"', 'id'), "
                        f"(SELECT MAX(id) FROM \"{table.name}\"))"
                    ))
    src.dispose()
    log.info("migration: copied %s", ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    return counts


def migrate_local_to_postgres_if_needed(engine: Engine, sqlite_path: Path) -> dict[str, int]:
    if engine.dialect.name != "postgresql" or not sqlite_path.exists():
        return {}
    return copy_database(f"sqlite:///{sqlite_path.as_posix()}", engine)
