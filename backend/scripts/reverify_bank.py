"""Solve every unverified AI-written bank question again with a second model, and retire the ones it disagrees with.

    python scripts/reverify_bank.py            # all unverified questions
    python scripts/reverify_bank.py --limit 200
    python scripts/reverify_bank.py --source practice --all   # imported banks (import_md_bank.py), checked or not

A question is written by one model and checked by another; when no second model could be reached it was kept as
unverified (question_bank.generate_batch), which is how a wrong key reached a JEE paper (28 October hard test).
Agreed: marked verified. Disagreed (or two correct options): retired by setting its reports to RETIRE_AFTER_REPORTS,
so no new paper picks it while old papers that used it still open. Safe to stop and run again.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.mock import BankQuestion  # noqa: E402
from app.services import question_bank as qb  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--source", default="ai", help="which questions: ai (default), practice (imported banks), ...")
    ap.add_argument("--all", action="store_true", help="also those already marked verified")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()
    db = SessionLocal()
    q = select(BankQuestion).where(func.coalesce(BankQuestion.reports, 0) < qb.RETIRE_AFTER_REPORTS,
                                   BankQuestion.source == args.source).order_by(BankQuestion.subject, BankQuestion.qtype)
    if not args.all:
        q = q.where(func.coalesce(BankQuestion.verified, False).is_(False))
    rows = db.scalars(q.limit(args.limit) if args.limit else q).all()
    kept = retired = unsure = 0
    for (subject, qtype), group in groupby(rows, key=lambda r: (r.subject, r.qtype)):
        group = list(group)
        for i in range(0, len(group), qb.BATCH):
            batch = group[i:i + qb.BATCH]
            items = [{"qtype": r.qtype, "subject": r.subject, "exam": r.exam, "question": r.question,
                      "options": r.options or [], "answer": r.answer} for r in batch]
            for r, verdict in zip(batch, qb.verify_batch(items, generator="", deadline=time.monotonic() + 300), strict=True):
                if verdict is True:
                    r.verified, kept = True, kept + 1
                elif verdict is False:
                    r.reports, retired = qb.RETIRE_AFTER_REPORTS, retired + 1
                    logging.info("retired #%s (%s): %s", r.id, subject, r.question[:90])
                else:
                    unsure += 1
            db.commit()
    print(f"verified {kept}, retired {retired}, still unchecked {unsure} of {len(rows)}")


if __name__ == "__main__":
    main()
