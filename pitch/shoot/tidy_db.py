"""For the filming database only: takes the "[Demo]" / "Demo:" labels off the seeded posts and titles (the video
carries its own "sample accounts" label instead) and gives the Pro accounts a Pro end date.

    python tidy_db.py <path to the filming server's sqlite file>

Refuses anything that isn't a local sqlite file, so it can't touch a real database.
"""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLUMNS = {
    "campus_posts": ["body"], "notifications": ["text"], "lecture_signals": ["text"],
    "study_sessions": ["title"], "study_rooms": ["name"], "flashcards": ["topic"],
}


def main(path: str) -> None:
    db_file = Path(path)
    if db_file.suffix != ".db" or not db_file.exists():
        raise SystemExit("Give the filming server's .db file.")
    db = sqlite3.connect(db_file)
    for table, cols in COLUMNS.items():
        for col in cols:
            n = db.execute(f"update {table} set {col} = replace(replace({col}, '[Demo] ', ''), 'Demo: ', '') "
                           f"where {col} like '%[Demo] %' or {col} like '%Demo: %'").rowcount
            if n:
                print(f"  {table}.{col}: {n} rows")
    until = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=24)).isoformat(sep=" ")
    db.execute("update users set pro_until = ? where plan = 'pro' and pro_until is null", (until,))
    db.commit()


if __name__ == "__main__":
    main(sys.argv[1])
