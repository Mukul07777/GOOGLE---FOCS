"""Last-day revision: what to revise when there is one day left before the exam, a mock or a class test.

The student picks the syllabus tomorrow's paper covers: all of it, one subject, or chosen chapters (narrowed down
to the topics that are coming, when they know them). The day is laid out from what that syllabus is worth and what
Focs knows about the student: which chapters they have studied (ticked in the Prep Hub, had lectures on, or lost
marks in), how each went in their tests and when it was last revised. Deterministic (no AI, no cost); only which
topics of a chapter papers ask most is the AI's judgement, made once per chapter and shared (services/likely.py).

What goes on the list ("cover"):
* Everything important (the default): the chapters the paper gives the most marks to, studied or not. A chapter not
  studied yet gets a short block for its most-asked topics only: on the last day the must-knows of a heavy chapter
  earn more than the rest of a light one.
* Only what has been studied: nothing new. Chapters not studied yet are listed under "leave these today".

The rules a good mentor follows on the last day:
* Marks first. A chapter is worth revising in proportion to its weightage, more so when the student's own tests
  show it is shaky or it hasn't been looked at for a while. In every chapter the most-asked topics come first.
* Every chapter on the list gets enough time to be worth opening (15 minutes at least) and none takes the day;
  part of the time is kept for the student's own mistakes, formulas and flashcards.
* The day ends with a test on exactly what was revised: its chapters, and only the topics listed for them.

The student shapes the list: chapters to add to today or take off it. Topics they got wrong in a recent test (their
weak spots) are pulled up the order.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.planner import Progress
from app.services.syllabus import Chapter, Syllabus, weight_label

STUDIED = 0.5              # at least half its topics ticked: a chapter the student can revise rather than learn
MIN_BLOCK, MAX_BLOCK = 15, 50  # minutes for one chapter
OWN_SHARE = 0.15           # of the day: redo queue, formula book, flashcards
HOURS = (2, 4, 6, 8, 10)
COVER = ("important", "studied")
FULL_BLOCK = 25            # about this long for a chapter the student has studied: more chapters than that is skimming
QUICK_BLOCK = 15           # a chapter not studied yet: its most-asked topics, from the capsule
TEST_SIZES = (10, 15, 20, 25, 30)

CHECKLIST = [
    {"id": "admit", "text": "Admit card printed, with the photo ID it names. Read its instructions once, slowly."},
    {"id": "centre", "text": "You know the way to the centre, how long it takes and the reporting time on the admit card."},
    {"id": "bag", "text": "Bag packed tonight: only what the admit card allows, nothing it bars."},
    {"id": "stop", "text": "Books closed by a fixed time this evening. No new topics, no late-night mock."},
    {"id": "sleep", "text": "At least seven hours of sleep. It is worth more marks than one more chapter."},
    {"id": "plan", "text": "Your paper plan is decided: which section first, and when to move on from a stuck question."},
]


COLLEGE_CHECKLIST = [
    {"id": "admit", "text": "Hall ticket and college ID in your bag. Check the date, the slot and the room on the date sheet once more."},
    {"id": "bag", "text": "Pens that work, pencil, eraser, scale, and a calculator of the kind this paper allows."},
    {"id": "centre", "text": "You have gone through the last two or three years' papers of this subject: the pattern repeats more than you'd think."},
    {"id": "stop", "text": "Books closed by a fixed time tonight. No new chapter now, however tempting."},
    {"id": "sleep", "text": "At least seven hours of sleep. It is worth more marks than one more chapter."},
    {"id": "plan", "text": "Your paper plan is decided: which questions first, how many minutes a mark, and ten minutes kept to read it over."},
]


@dataclass
class Accuracy:
    correct: int = 0
    attempted: int = 0

    @property
    def percent(self) -> int | None:
        return round(100 * self.correct / self.attempted) if self.attempted >= 3 else None  # fewer says nothing


def _studied(ch: Chapter, progress: Progress) -> float:
    return sum(t.id in progress.done_topics for t in ch.topics) / max(1, len(ch.topics))


def _last_look(ch: Chapter, progress: Progress, before: date) -> date | None:
    """The last day before ``before`` that the chapter was revised or one of its topics was studied on Focs."""
    days = list(progress.revisions.get(ch.id, [])) + [d for t in ch.topics if (d := progress.done_topics.get(t.id)) and d > date.min]
    days = [d for d in days if d < before]
    return max(days) if days else None


def _shaky(accuracy: int | None, unknown: float = 0.2) -> float:
    return unknown if accuracy is None else 1.0 if accuracy < 40 else 0.6 if accuracy < 60 else 0.3 if accuracy < 75 else 0.0


def _priority(ch: Chapter, studied: float, accuracy: int | None, idle_days: int | None, misses: int = 0) -> float:
    stale = 0.6 if idle_days is None else 0.4 if idle_days > 30 else 0.2 if idle_days > 7 else 0.0
    weak = min(1.0, 0.5 + 0.15 * misses) if misses else 0.0  # got it wrong in a recent test and hasn't cleared it yet
    return ch.weight * studied * (1 + _shaky(accuracy) + stale + weak)


def _reasons(ch: Chapter, studied: float, accuracy: int | None, idle_days: int | None, misses: int = 0,
             lecture: bool = False, quick: bool = False, ranked: bool = False, cover: str = "important") -> list[str]:
    out = [f"{weight_label(ch.weight).capitalize()} weightage"]
    if misses:
        out.append("a weak spot from your last test")
    if accuracy is not None:
        out.append(f"{accuracy}% in your tests")
    if quick:  # nothing of it studied: there is no revising "what you've done", only its must-knows
        out.append("not studied yet: its most-asked topics only" if ranked else "not studied yet: its capsule only")
        return out
    if idle_days is None:
        out.append("never revised")
    elif idle_days > 7:
        out.append(f"last looked at {idle_days} days ago")
    if cover == "studied":
        if lecture and studied < STUDIED:
            out.append("from your lectures: revise what they covered")
        elif studied < 1:
            out.append(f"{max(1, round(100 * studied))}% studied: revise only what you've done")
    elif lecture and studied < STUDIED:
        out.append("from your lectures")
    elif studied == 0:
        out.append("not studied yet")
    elif studied < 1:
        out.append(f"{max(1, round(100 * studied))}% studied")
    return out


LONG_BLOCK = 180  # minutes: the most one chapter gets when only a few chapters are being tested


def _spread(scores: list[float], minutes: int, most: int = MAX_BLOCK) -> list[int]:
    """Minutes for each chapter, in proportion to its priority, each between MIN_BLOCK and ``most``, in fives. A
    chapter lifted to MIN_BLOCK takes that time from the others, so a long list still adds up to the day; time a
    chapter can't use past ``most`` is left over rather than handed on (a chapter narrowed down to one topic never
    gets more than the whole of it would)."""
    lifted: set[int] = set()
    while True:
        rest = [i for i in range(len(scores)) if i not in lifted]
        left = minutes - MIN_BLOCK * len(lifted)
        total = sum(scores[i] for i in rest) or 1
        share = {i: left * scores[i] / total for i in rest}
        low = {i for i, m in share.items() if m < MIN_BLOCK}
        if not low:
            break
        lifted |= low
    return [int(max(MIN_BLOCK, min(most, round(share.get(i, MIN_BLOCK) / 5) * 5))) for i in range(len(scores))]


def _interleave(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the priority order but never three chapters of one subject in a row: a change of subject is a rest."""
    out: list[dict[str, Any]] = []
    waiting = list(rows)
    while waiting:
        last_two = [r["subject"] for r in out[-2:]]
        pick = next((r for r in waiting if not (len(last_two) == 2 and last_two[0] == last_two[1] == r["subject"])), waiting[0])
        waiting.remove(pick)
        out.append(pick)
    return out


def _ref(c: Chapter, quick: bool | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"id": c.id, "name": c.name, "subject": c.subject, "weightage": weight_label(c.weight)}
    if quick is not None:
        out["quick"] = quick
    return out


def build(syl: Syllabus, progress: Progress, today: date, *, hours: float = 6, subject: str | None = None,
          chapter_ids: list[str] | None = None, accuracy: dict[tuple[str, str], Accuracy] | None = None,
          exam_date: date | None = None, capsules: set[str] | None = None, topic_ids: list[str] | None = None,
          include: list[str] | None = None, exclude: list[str] | None = None, weak: dict[str, int] | None = None,
          lectures: dict[str, set[str]] | None = None, asked: dict[str, list[str]] | None = None,
          cover: str = "important") -> dict[str, Any]:
    """``topic_ids``: the topics that are coming (a chapter with some of its topics named is revised for those only).
    ``include`` / ``exclude``: chapters the student added to today's list or took off it.
    ``weak``: chapter id → questions missed there in recent tests and not yet cleared.
    ``lectures``: chapter id → the topics of it the student's captured lectures were about (empty: no one topic).
    ``asked``: chapter id → its most-asked topic ids, most asked first (services/likely.py).
    ``cover``: "important" (the chosen syllabus by marks, studied or not) or "studied" (only what has been studied).
    A chapter the student had a lecture on, or was tested on and missed questions in, counts as studied however
    few of its topics are ticked: there is something to revise. A chosen chapter is tomorrow's test: never "new"."""
    accuracy, capsules, weak, lectures, asked = accuracy or {}, capsules or set(), weak or {}, lectures or {}, asked or {}
    cover = cover if cover in COVER else "important"
    wanted_topics = set(topic_ids or [])
    include = [c for c in dict.fromkeys(include or []) if c in syl.by_id]
    exclude = {c for c in exclude or [] if c in syl.by_id} - set(include)
    chosen = [c for c in chapter_ids or [] if c in syl.by_id]
    if chosen:
        scope, pool = "chapters", [syl.by_id[c] for c in chosen]
    elif subject in syl.subjects:
        scope, pool = "subject", syl.subject_chapters(subject)
    else:
        scope, subject, pool = "all", None, list(syl.chapters)

    pool = pool + [syl.by_id[c] for c in include if all(c != p.id for p in pool)]
    rows, not_studied, removed = [], [], []
    for ch in pool:
        if ch.id in exclude:
            removed.append(ch)
            continue
        studied = _studied(ch, progress)
        new = studied < STUDIED and not (ch.id in lectures or ch.id in weak) and scope != "chapters"
        if new and cover == "studied" and ch.id not in include:  # added by hand: on the list whatever its state
            not_studied.append(ch)
            continue
        quick = new and cover == "important"
        order = {tid: i for i, tid in enumerate(asked.get(ch.id, []))}
        hot = sorted((t for t in ch.topics if t.id in order), key=lambda t: order[t.id])
        first = hot + [t for t in ch.topics if t.id not in order]  # the most-asked topics lead
        named = [t for t in first if t.id in wanted_topics]  # the topics of this chapter that are coming
        heard = lectures.get(ch.id, set())
        if named:
            topics = named
        elif quick:
            topics = hot or first
        elif cover == "studied":
            topics = [t for t in first if t.id in progress.done_topics or t.id in heard] or first
        else:
            topics = first
        part = named or (hot if quick else [])
        share = max(0.34, len(part) / len(ch.topics)) if part else 1.0  # two topics of nine need less than the chapter
        acc = accuracy.get((ch.subject, ch.name), Accuracy()).percent
        revised_today = today in progress.revisions.get(ch.id, [])
        # ticking a chapter off must not reshuffle the day's list: rank it as it stood this morning
        look = _last_look(ch, progress, before=today)
        idle = (today - look).days if look else None
        misses = weak.get(ch.id, 0)
        if quick:  # nothing of the student's to go on: the marks it carries, and a test that went badly
            score = ch.weight * (1 + _shaky(acc, unknown=0.0))
        else:
            score = _priority(ch, max(studied, 0.25) if cover == "studied" else 1.0, acc, idle, misses)
        rows.append({"id": ch.id, "name": ch.name, "subject": ch.subject, "weightage": weight_label(ch.weight),
                     "accuracy": acc, "studied": round(100 * studied), "revised_today": revised_today,
                     "reasons": _reasons(ch, studied, acc, idle, misses, ch.id in lectures, quick, bool(hot), cover),
                     "has_capsule": ch.id in capsules,
                     "topics": [{"id": t.id, "name": t.name, "done": t.id in progress.done_topics, "asked": t.id in order}
                                for t in topics],
                     "topic_count": len(ch.topics), "topics_chosen": bool(named), "quick": quick,
                     "added": ch.id in include, "weak": bool(misses),
                     # the order goes by what a chapter is worth tomorrow (two named topics of nine are worth less);
                     # its time by how much of it there is to go through today
                     "_rank": score * (share if named else 1.0), "_need": score * share,
                     # a test on chosen chapters is the whole of tomorrow: as many of them as the day holds, each at
                     # the least time worth opening it for, and what is left over goes to the ones worth most
                     "_block": QUICK_BLOCK if quick else MIN_BLOCK if scope == "chapters" else FULL_BLOCK})
    rows.sort(key=lambda r: -r["_rank"])

    minutes = int(hours * 60)
    own = int(max(20, min(60, round(minutes * OWN_SHARE / 5) * 5)))
    available = max(MIN_BLOCK, minutes - own)
    count = used = 0
    for r in rows:  # most marks first, as many as the day holds; a chapter not studied yet takes a shorter block
        if count and used + r["_block"] > available:
            break
        used += r["_block"]
        count += 1
    planned = rows[:count] + [r for r in rows[count:] if r["added"]]  # what the student added stays, whatever the hours
    later = [r for r in rows[count:] if not r["added"]]
    # a test on a few chosen chapters is the whole of tomorrow: they share the time there is, not 50 minutes each
    most = max(MAX_BLOCK, min(LONG_BLOCK, available // max(1, len(planned)) // 5 * 5)) if scope == "chapters" else MAX_BLOCK
    for row, m in zip(planned, _spread([r["_need"] for r in planned], available, most), strict=True):
        row["minutes"] = m
    planned = _interleave(planned)
    for r in rows:
        for k in ("_rank", "_need", "_block"):
            r.pop(k)

    worth = sum(c.weight for c in syl.chapters) or 1
    covered = {r["id"] for r in planned}
    return {
        "scope": scope, "subject": subject, "hours": hours, "hour_choices": list(HOURS), "cover": cover,
        "exam_date": exam_date.isoformat() if exam_date else None,
        "days_left": (exam_date - today).days if exam_date else None,
        "chapters": planned,                       # today's revision order
        "if_time": [_ref(syl.by_id[r["id"]], r["quick"]) for r in later],  # next in line by marks: the student may add any
        "leave": [_ref(c) for c in sorted(not_studied, key=lambda c: -c.weight)],  # all of them: the student may add any
        "leave_count": len(not_studied),
        "removed": [_ref(c) for c in removed],
        "minutes": {"chapters": sum(r["minutes"] for r in planned), "own": own, "total": minutes},
        "revised": sum(r["revised_today"] for r in planned),
        "paper_share": round(100 * sum(c.weight for c in syl.chapters if c.id in covered) / worth),
        "checklist": COLLEGE_CHECKLIST if syl.is_college else CHECKLIST,
        "test_sizes": list(TEST_SIZES),
    }


def test_parts(plan: dict[str, Any], count: int) -> list[dict[str, Any]]:
    """What a test on the day's list covers, subject by subject: the chapters on it, the topics of a chapter when only
    some of them are listed (one narrowed down, one not studied yet), and how many of the ``count`` questions each
    subject gets: one each first, then in proportion to its time on the list. With more subjects than questions,
    the ones with the most time on the list."""
    parts: dict[str, dict[str, Any]] = {}
    for r in plan["chapters"]:
        part = parts.setdefault(r["subject"], {"subject": r["subject"], "chapters": [], "topics": {}, "minutes": 0})
        part["chapters"].append(r["name"])
        part["minutes"] += r["minutes"]
        if len(r["topics"]) < r["topic_count"]:
            part["topics"][r["name"]] = [t["name"] for t in r["topics"]]
    kept = sorted(parts.values(), key=lambda p: -p["minutes"])[:count]
    spare = count - len(kept)
    total = sum(p["minutes"] for p in kept) or 1
    raw = {p["subject"]: spare * p["minutes"] / total for p in kept}
    extra = {s: int(v) for s, v in raw.items()}
    for s in sorted(raw, key=lambda s: raw[s] - extra[s], reverse=True)[: spare - sum(extra.values())]:
        extra[s] += 1
    return [{"subject": p["subject"], "chapters": p["chapters"], "topics": p["topics"], "count": 1 + extra[p["subject"]]}
            for p in parts.values() if p["subject"] in extra]  # in the order of the day's list
