"""The correct answers of a test on the filming database, in the paper's order, so the filmed student can answer
like a real one (mostly right, a few confidently wrong for the gap map).

    python answers.py <filming .db file> <test id>   -> JSON list: option index (MCQ) or value (numerical)
"""
import json
import sqlite3
import sys
from pathlib import Path

db_file, test_id = Path(sys.argv[1]), int(sys.argv[2])
if db_file.suffix != ".db":
    raise SystemExit("Give the filming server's .db file.")
db = sqlite3.connect(db_file)
ids = json.loads(db.execute("select question_ids from mock_tests where id = ?", (test_id,)).fetchone()[0] or "[]")
rows = dict(db.execute(f"select id, answer from bank_questions where id in ({','.join('?' * len(ids))})", ids).fetchall()) if ids else {}
print(json.dumps([rows.get(i) for i in ids]))
