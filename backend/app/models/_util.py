from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no timezone type; the API serialises it with a 'Z')."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
