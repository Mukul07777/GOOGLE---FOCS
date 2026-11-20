"""The three demo numbers, measured rather than estimated.

    python scripts/demo_metrics.py cost [--days 30]
        Cost per lecture hour, from the cost ledger (every AI call is recorded with its list-price cost). Reads the
        database in backend/.env (DATABASE_URL), so run it where the app runs, or point DATABASE_URL at Supabase.

    python scripts/demo_metrics.py drive [--url http://127.0.0.1:8000] [--boards 4] [--audio lecture-25s.webm]
        Plays a scripted lecture into a running Focs, the way the browser does (a frame every 5 s, "settle" once a
        growing board is still), and times:
          - board to note: a new board appears -> its notes come back
          - finished writing to final note: the teacher's last line -> the updated notes (includes the settle wait)
          - caption delay (with --audio): the recorder's 25 s piece + the time to transcribe it
        Uses a throwaway account unless --email/--password are given.

Paste the printed table into the pitch as it is: it says what was measured, on what, and when.
"""
from __future__ import annotations

import argparse
import io
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CHUNK_S = 25  # the voice lane records the lecture's sound in pieces this long (frontend/src/lib/audio.ts)
LIVE_SOURCES = ("screen", "camera")


# --------------------------------------------------------------------------------------------- cost per lecture hour
def lecture_costs(db, days: int = 30, min_minutes: float = 5.0) -> list[dict]:
    """Every ended live lecture of the last `days`: its length and what its owner's AI calls cost while it ran
    (from the start until two minutes after the end, so the revision sheet written on ending is counted)."""
    from sqlalchemy import func, select

    from app.models._util import utcnow
    from app.models.llm_call import LlmCall
    from app.models.session import StudySession

    since = utcnow() - timedelta(days=days)
    sessions = db.scalars(select(StudySession).where(
        StudySession.ended_at.is_not(None), StudySession.started_at >= since, StudySession.source.in_(LIVE_SOURCES))).all()
    out = []
    for s in sessions:
        hours = (s.ended_at - s.started_at).total_seconds() / 3600
        if hours * 60 < min_minutes:
            continue
        window = (LlmCall.user_id == s.user_id, LlmCall.created_at >= s.started_at, LlmCall.created_at <= s.ended_at + timedelta(minutes=2))
        usd = db.scalar(select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0)).where(*window)) or 0.0
        calls = db.scalar(select(func.count(LlmCall.id)).where(*window)) or 0
        out.append({"session_id": s.id, "source": s.source, "hours": hours, "usd": float(usd), "calls": int(calls)})
    return out


def summarize_costs(rows: list[dict], usd_inr: float) -> dict:
    hours = sum(r["hours"] for r in rows)
    usd = sum(r["usd"] for r in rows)
    per_hour = [r["usd"] / r["hours"] for r in rows if r["hours"] > 0]
    return {
        "lectures": len(rows), "hours": round(hours, 2), "usd": round(usd, 4),
        "usd_per_hour": round(usd / hours, 4) if hours else None,
        "inr_per_hour": round(usd / hours * usd_inr, 2) if hours else None,
        "median_usd_per_hour": round(statistics.median(per_hour), 4) if per_hour else None,
    }


def cost_command(args) -> None:
    from app.core.config import settings
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        rows = lecture_costs(db, args.days)
    if not rows:
        print(f"No ended live lectures of 5+ minutes in the last {args.days} days. Run a real one first.")
        return
    s = summarize_costs(rows, settings.USD_INR)
    print(f"| Measured {datetime.now():%Y-%m-%d} from the cost ledger | |")
    print("|---|---|")
    print(f"| Live lectures | {s['lectures']} ({s['hours']} h) |")
    print(f"| AI cost, all of them | ${s['usd']:.4f} |")
    print(f"| **Cost per lecture hour** | **${s['usd_per_hour']:.4f} (₹{s['inr_per_hour']:.2f})**, median ${s['median_usd_per_hour']:.4f} |")
    print("\nPer lecture:")
    for r in sorted(rows, key=lambda r: -r["usd"]):
        print(f"  #{r['session_id']:<6} {r['source']:<7} {r['hours'] * 60:5.1f} min  {r['calls']:4d} calls  ${r['usd']:.4f}")


# --------------------------------------------------------------------------------------------- latency, end to end
BOARDS = [
    ["Newton's second law", "F = m a", "Unit of force: newton (N)", "1 N = 1 kg m/s^2"],
    ["Work done by a force", "W = F s cos θ", "Unit: joule (J)", "No work if F is perpendicular to s"],
    ["Kinetic energy", "K = 1/2 m v^2", "Work-energy theorem: W = ΔK", "K is never negative"],
    ["Ohm's law", "V = I R", "Unit of resistance: ohm (Ω)", "Resistors in series add up"],
    ["Ideal gas equation", "P V = n R T", "R = 8.314 J/(mol K)", "T is in kelvin"],
    ["Snell's law", "n1 sin i = n2 sin r", "Critical angle: sin C = 1/n", "Total internal reflection"],
]


def board(lines: list[str]) -> bytes:
    """A chalkboard with these lines, like a lecture frame."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1280, 720), (28, 52, 42))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 54)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((90, 80 + i * 110), line, font=font, fill=(240, 240, 235))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class Lecture:
    """One live lecture on a running Focs, driven like the browser drives it."""

    def __init__(self, url: str, email: str | None, password: str | None, interval: float):
        import httpx

        self.http = httpx.Client(base_url=url.rstrip("/") + "/api", timeout=180)
        self.interval = interval
        if not email:
            email, password = f"demo.metrics.{int(time.time())}@example.com", "demo-metrics-123"
            r = self.http.post("/auth/register", json={"email": email, "full_name": "Demo Metrics", "password": password,
                                                       "exam_target": "jee", "class_level": "Class 12", "accepted_terms": True})
        else:
            r = self.http.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        self.http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        self.health = self.http.get("/health").json()
        self.session = self.http.post("/sessions", json={"title": "Demo metrics", "source": "screen"}).json()["id"]

    def frame(self, jpeg: bytes) -> dict:
        r = self.http.post(f"/capture/{self.session}/frame", files={"frame": ("frame.jpg", jpeg, "image/jpeg")})
        r.raise_for_status()
        return r.json()

    def show(self, jpeg: bytes, until_text: str, limit_s: float) -> float | None:
        """Put this board on screen and keep it there, as the browser does: send it once (again only if the server
        was busy), then call settle once it has been still for settle_after. Seconds from the first frame until a note
        containing `until_text` comes back, or None if none did within `limit_s`."""
        t0 = time.monotonic()
        key = "".join(until_text.lower().split())
        res, settle_at = self.frame(jpeg), None
        while True:
            note = res.get("note") or {}
            text = "".join(f"{note.get('ocr_raw') or ''} {note.get('ai_notes') or ''}".lower().split())
            if res.get("status") in ("created", "updated") and key in text:
                return time.monotonic() - t0
            if res.get("status") == "growing":
                settle_at = time.monotonic() + float(res.get("settle_after") or 20)
            elif res.get("status") != "busy" and settle_at is None:
                return None  # read, and nothing is pending: this board will not produce that note
            time.sleep(self.interval)  # the browser's next tick
            if time.monotonic() - t0 > limit_s:
                return None
            if res.get("status") == "busy":
                res = self.frame(jpeg)
            elif settle_at is not None and time.monotonic() >= settle_at:
                res, settle_at = self.http.post(f"/capture/{self.session}/settle").json(), None
            else:
                res = {"status": "waiting"}

    def caption(self, audio: Path) -> float | None:
        t0 = time.monotonic()
        mime = "audio/webm" if audio.suffix == ".webm" else "audio/wav" if audio.suffix == ".wav" else "audio/mpeg"
        r = self.http.post(f"/capture/{self.session}/audio", files={"audio": (audio.name, audio.read_bytes(), mime)},
                           data={"start_s": "0", "end_s": str(CHUNK_S)})
        r.raise_for_status()
        return None if r.json().get("skipped") else time.monotonic() - t0

    def end(self) -> None:
        self.http.post(f"/sessions/{self.session}/end")


def drive_command(args) -> None:
    lec = Lecture(args.url, args.email, args.password, args.interval)
    ai = lec.health.get("llm", {})
    print(f"Focs {lec.health.get('version')} at {args.url} · AI: {ai.get('model') if ai.get('available') else 'off (offline notes)'}"
          f" · OCR: {', '.join(lec.health.get('ocr', {}).get('engines', []))}")
    new_board, finished = [], []
    try:
        for k in range(args.boards):
            lines = BOARDS[k % len(BOARDS)]
            # a new board, already half written: how long until its notes come back
            t = lec.show(board(lines[:2]), lines[1], limit_s=90)
            print(f"  board {k + 1}: new board -> notes      {'%.1f s' % t if t is not None else 'no note in 90 s'}")
            if t is not None:
                new_board.append(t)
            # the teacher writes the rest: from the last line to the final notes (waits for the board to settle)
            t = lec.show(board(lines), lines[-1], limit_s=120)
            print(f"           last line -> final notes  {'%.1f s' % t if t is not None else 'no update in 120 s'}")
            if t is not None:
                finished.append(t)
        captions = []
        if args.audio:
            for _ in range(args.audio_runs):
                t = lec.caption(Path(args.audio))
                if t is None:
                    print("  captions: skipped (no speech-to-text key, allowance used up, or silence)")
                    break
                captions.append(CHUNK_S + t)
    finally:
        lec.end()

    def cell(xs: list[float]) -> str:
        return f"median {statistics.median(xs):.1f} s, worst {max(xs):.1f} s (n={len(xs)})" if xs else "not measured"

    print(f"\n| Measured {datetime.now():%Y-%m-%d} on {args.url} | |")
    print("|---|---|")
    print(f"| New board -> its notes | {cell(new_board)} |")
    print(f"| Teacher's last line -> final notes | {cell(finished)} (includes the wait for the board to settle, BOARD_SETTLE_S, by design) |")
    print(f"| Teacher speaks -> caption | {cell(captions)} (a {CHUNK_S} s recording piece + transcription) |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cost", help="cost per lecture hour from the ledger")
    c.add_argument("--days", type=int, default=30)
    d = sub.add_parser("drive", help="time a scripted lecture on a running Focs")
    d.add_argument("--url", default="http://127.0.0.1:8000")
    d.add_argument("--email")
    d.add_argument("--password")
    d.add_argument("--boards", type=int, default=4)
    d.add_argument("--interval", type=float, default=5.0, help="seconds between frames (the app's default is 5)")
    d.add_argument("--audio", help="a ~25 s recording of a teacher speaking (webm, wav or mp3)")
    d.add_argument("--audio-runs", type=int, default=3)
    args = ap.parse_args()
    cost_command(args) if args.cmd == "cost" else drive_command(args)


if __name__ == "__main__":
    main()
