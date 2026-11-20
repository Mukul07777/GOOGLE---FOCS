"""The mentor plan: from a student's goal, time and progress to a month-by-month, week-by-week and daily plan.

Deterministic (no AI, no cost) and rebuilt from current progress every time it's asked for, so falling behind or
getting ahead simply reshapes the rest of the plan. How the time is spent:

* Learning phase, until a revision window before the exam: ~75% learning and practising chapters, ~15% spaced
  revision (a week, a month and three months after a chapter is finished), ~10% tests (chapter tests, then full
  mocks once enough of the syllabus is done).
* All subjects advance in parallel, each getting time in proportion to the work it has left, so they finish
  together. Chapter order depends on the student: school order in Class 11, Class 12 chapters alongside the
  Class 11 backlog in Class 12, and foundations first then highest weightage per hour for droppers.
* Revision window (4-12 weeks before the exam): full revision and frequent full mocks.

The student can edit the plan, and every edit is just another input here: their own hours for each day of the
week, chapters to take next ("pinned", ahead of the mentor's order), chapters to leave out ("skipped"), and for
today's list their own extra tasks and the planned ones they don't want today.

A college student's plan is the same engine pointed at one semester: the syllabus is their subjects, the exam is
their mid-semester or end-semester exams, the revision window is one to two weeks, a subject's chapters are taken
in the order they are taught, and the "mock" is a subject test.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.services.syllabus import SCHOOL, Chapter, Syllabus, group, has_tests, is_college, is_placement, is_school, weight_label

LEARN_SHARE, REVISE_SHARE, TEST_SHARE = 0.75, 0.15, 0.10
MOCK_HOURS = 4.5  # a 3-hour paper and its analysis
SUBJECT_TEST_HOURS = 1.5  # college: a test on one subject and going through it
SPACED_DAYS = (7, 30, 90)
COLLEGE_TRACK = "college"

TRACKS: dict[str, dict[str, str]] = {
    "jee_main": {"exam": "jee", "label": "JEE Main"},
    "jee_advanced": {"exam": "jee", "label": "JEE Main + Advanced"},
    "neet": {"exam": "neet", "label": "NEET UG"},
}

# Rules of thumb for the study hours a goal usually takes (including coaching classes). Cut-offs move every year.
TARGETS: dict[str, list[dict[str, Any]]] = {
    "jee": [
        {"id": "air_1k", "label": "AIR under 1,000", "hint": "Top IITs and branches", "hours": 8},
        {"id": "air_10k", "label": "AIR under 10,000", "hint": "IITs and the top NITs", "hours": 7},
        {"id": "air_50k", "label": "AIR under 50,000", "hint": "NITs and IIITs", "hours": 6},
        {"id": "qualify", "label": "Qualify for JEE Advanced", "hint": "Clear the JEE Main cut-off", "hours": 5},
        {"id": "college", "label": "A good engineering college", "hint": "Through JEE Main or state exams", "hours": 4},
    ],
    "neet": [
        {"id": "air_1k", "label": "AIR under 1,000", "hint": "AIIMS and the top government colleges", "hours": 9},
        {"id": "air_10k", "label": "AIR under 10,000", "hint": "Top government medical colleges", "hours": 8},
        {"id": "govt_mbbs", "label": "A government MBBS seat", "hint": "The rank it takes depends on category and state quota", "hours": 7},
        {"id": "qualify", "label": "Qualify NEET", "hint": "Private and deemed colleges, BDS, AYUSH", "hours": 5},
    ],
    # hours of self-study a day, outside classes and labs
    "college": [
        {"id": "sgpa_9", "label": "9+ SGPA", "hint": "Top of the class: A or better in almost every course", "hours": 4},
        {"id": "sgpa_8", "label": "8+ SGPA", "hint": "Strong grades, and safe for most placement cut-offs", "hours": 3},
        {"id": "sgpa_7", "label": "7+ SGPA", "hint": "Comfortably above the usual 7.0 cut-off", "hours": 2},
        {"id": "clear", "label": "Clear every paper", "hint": "No backlogs this semester", "hours": 1.5},
    ],
}


TARGETS["gate"] = [
    {"id": "air_100", "label": "AIR under 100", "hint": "IISc and the old IITs, M.Tech in the branch you want", "hours": 7},
    {"id": "air_1k", "label": "AIR under 1,000", "hint": "IIT M.Tech, and the top PSUs' shortlists", "hours": 6},
    {"id": "psu", "label": "A PSU call or an NIT seat", "hint": "A score well clear of the cut-off", "hours": 5},
    {"id": "qualify", "label": "Qualify GATE", "hint": "Clear the cut-off: a valid score for three years", "hours": 3},
]
TARGETS["cbse"] = [
    {"id": "pct_95", "label": "95% and above", "hint": "Among the very best in every subject", "hours": 5},
    {"id": "pct_90", "label": "90% and above", "hint": "A strong result in every subject", "hours": 4},
    {"id": "pct_75", "label": "75% and above", "hint": "Comfortable in every subject", "hours": 3},
    {"id": "pass", "label": "Pass every subject well", "hint": "No compartment, no stress", "hours": 2},
]
# hours of preparation a day, alongside college
TARGETS["placement"] = [
    {"id": "top_product", "label": "A top product company", "hint": "Hard DSA rounds, system design and strong projects", "hours": 5},
    {"id": "product", "label": "A product company or a funded start-up", "hint": "Medium-to-hard DSA and solid core subjects", "hours": 4},
    {"id": "service_plus", "label": "A higher-package role at a service company", "hint": "The specialist tracks: a tougher coding round than the base offer", "hours": 3},
    {"id": "placed", "label": "Get placed", "hint": "Clear the aptitude test, a coding round and the interviews", "hours": 2},
]
# hours of preparation a day (many SSC aspirants work or study alongside)
TARGETS["ssc_cgl"] = [
    {"id": "group_b", "label": "A Group B post", "hint": "ASO, Income Tax or GST Inspector: a high Tier-II score", "hours": 7},
    {"id": "any_post", "label": "Any CGL post", "hint": "Clear the cut-off for a Group B or C post", "hours": 5},
    {"id": "tier2", "label": "Clear Tier-I", "hint": "Get called for Tier-II", "hours": 4},
    {"id": "practice", "label": "Start the basics", "hint": "A first attempt, building speed in all four sections", "hours": 3},
]
OWN_TRACKS = ("college", "gate", "cbse", "placement", "ssc_cgl")  # tracks whose exam is the one the student chose in their profile


def family(exam: str) -> str:
    """Which goals, pace and wording an exam uses: every college branch shares one, every GATE paper another."""
    return group(exam) or exam


def gate_exam_date(today: date) -> date:
    """GATE is held over the first two weekends of February: the coming first Saturday of February."""
    for year in (today.year, today.year + 1, today.year + 2):
        d = date(year, 2, 1)
        d += timedelta(days=(5 - d.weekday()) % 7)
        if d > today + timedelta(days=14):
            return d
    raise AssertionError


def placement_dates(today: date) -> list[tuple[date, str]]:
    """When drives usually begin: most colleges open the season in August, internship drives follow, and the IITs
    start on 1 December. A student sets their own college's date over these."""
    rounds = (((8, 1), "Placement season opens (most colleges)"), ((9, 15), "Internship drives"), ((12, 1), "IIT placements begin"))
    days = sorted((date(y, m, d), name) for y in (today.year, today.year + 1) for (m, d), name in rounds)
    return [r for r in days if r[0] > today + timedelta(days=14)][:3]


def ssc_dates(today: date) -> list[tuple[date, str]]:
    """When SSC CGL is usually held (approximate: SSC's own calendar sets each year's dates): Tier-I in the summer,
    Tier-II towards the end of the year."""
    rounds = (((6, 15), "SSC CGL Tier-I"), ((10, 15), "SSC CGL Tier-II"))
    days = sorted((date(y, m, d), name) for y in (today.year, today.year + 1) for (m, d), name in rounds)
    return [r for r in days if r[0] > today + timedelta(days=14)][:3]


def board_exam_dates(today: date, cls: int) -> list[tuple[date, str]]:
    """Class 10 and 12 boards start in mid-February, after pre-boards in December; every other class has its finals in
    early March, after half-yearlies in September."""
    board = cls in (10, 12)
    rounds = [((2, 15), "Board exams")] if board else [((3, 1), "Final exams")]
    rounds += [((9, 15), "Half-yearly exams"), ((12, 10), "Pre-boards" if board else "Unit tests round 2")]
    days = sorted((date(y, m, d), name) for y in (today.year, today.year + 1) for (m, d), name in rounds)
    return [r for r in days if r[0] > today + timedelta(days=7)][:3]

# questions a student gets through in an hour of practice
QUESTIONS_PER_HOUR = {"Physics": 8, "Chemistry": 10, "Mathematics": 8, "Biology": 25}
NEET_QPH = {"Physics": 12, "Chemistry": 15, "Biology": 25}

# subjects studied on each day of a 3-day cycle (NEET: Biology every day)
ROTATION = {
    "jee": (("Physics", "Mathematics"), ("Chemistry", "Physics"), ("Mathematics", "Chemistry")),
    "neet": (("Biology", "Physics"), ("Biology", "Chemistry")),
}


def school_hours_share(exam: str | None) -> float:
    """Self-study a school class can sensibly do, as a share of the board-class hours in TARGETS["cbse"] (a Class 1
    child was told 34 h a week was what 90% takes)."""
    n = SCHOOL.get(exam or "")
    if not n:
        return 1.0
    return 0.25 if n <= 2 else 0.4 if n <= 5 else 0.6 if n <= 8 else 0.85 if n <= 10 else 1.0


def target_info(exam: str, target: str) -> dict[str, Any]:
    bands = TARGETS[family(exam)]
    t = next((t for t in bands if t["id"] == target), bands[-1])
    share = school_hours_share(exam)
    return t if share == 1.0 else {**t, "hours": round(t["hours"] * share * 2) / 2}


def _cycle(exam: str, subjects: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """The subjects studied on each day of the rotation. College: two a day, working round all of them."""
    if exam in ROTATION:
        return ROTATION[exam]
    if len(subjects) <= 2:
        return (tuple(subjects),)
    return tuple((subjects[(2 * d) % len(subjects)], subjects[(2 * d + 1) % len(subjects)]) for d in range(len(subjects)))


def _first_sunday_of_may(year: int) -> date:
    d = date(year, 5, 1)
    return d + timedelta(days=(6 - d.weekday()) % 7)


JEE_SESSIONS = ((1, 22), (4, 4))  # JEE Main session 1 (late January) and session 2 (early April), approximate


def exam_dates(track: str, year: int) -> list[date]:
    """The approximate exam days of a year: NEET on the first Sunday of May, JEE Main's two sessions."""
    if track == "neet":
        return [_first_sunday_of_may(year)]
    return [date(year, m, d) for m, d in JEE_SESSIONS]


def default_exam_date(track: str, class_level: str, today: date) -> date:
    """The student's next attempt: two exam seasons away in Class 11, the coming one in Class 12 or as a dropper.
    For JEE, session 1 when it is at least five months away, otherwise session 2 (January becomes a rehearsal)."""
    ahead = 2 if class_level == "11" else 1
    year = today.year + (ahead if today.month >= 4 else ahead - 1)
    while True:
        days = exam_dates(track, year)
        if track == "neet":
            if days[0] > today + timedelta(days=14):
                return days[0]
        else:
            if days[0] >= today + timedelta(days=150):
                return days[0]
            if days[1] > today + timedelta(days=14):
                return days[1]
        year += 1


# College exams, roughly as Indian universities hold them: an odd semester from August to December and an even one
# from January to May, each with a mid-semester and an end-semester round. Every college's dates differ a little.
COLLEGE_EXAMS = (((3, 1), "Mid-semester exams"), ((5, 5), "End-semester exams"),
                 ((9, 25), "Mid-semester exams"), ((11, 25), "End-semester exams"))


def college_exam_dates(today: date, count: int = 3) -> list[tuple[date, str]]:
    """The next few exam rounds, soonest first (at least a week away: nearer than that is last-day revision)."""
    rounds = sorted((date(year, m, d), name) for year in (today.year, today.year + 1) for (m, d), name in COLLEGE_EXAMS)
    return [r for r in rounds if r[0] > today + timedelta(days=7)][:count]


def default_college_exam_date(today: date) -> date:
    """The coming end-semester exams, or the ones after when these are under three weeks away."""
    return next(d for d, name in college_exam_dates(today, 8) if name.startswith("End") and d > today + timedelta(days=21))


@dataclass
class Goal:
    exam: str
    track: str
    class_level: str
    exam_date: date
    target: str
    weekday_hours: float
    weekend_hours: float
    # the student's edits (see the module docstring)
    day_hours: tuple[float, ...] | None = None   # hours for Monday…Sunday, when set day by day
    pinned: tuple[str, ...] = ()                 # chapter ids to study next, first one first
    skipped: frozenset[str] = frozenset()        # chapter ids left out of the plan

    @property
    def by_day(self) -> tuple[float, ...]:
        """Planned hours for Monday…Sunday."""
        return self.day_hours or (self.weekday_hours,) * 5 + (self.weekend_hours,) * 2

    @property
    def weekly_hours(self) -> float:
        return sum(self.by_day)

    def hours_on(self, day: date) -> float:
        return self.by_day[day.weekday()]

    @property
    def college(self) -> bool:
        return is_college(self.exam)

    @property
    def subject_tests(self) -> bool:
        """Tested one subject at a time (a semester's papers, the boards, placement rounds), not by one full mock."""
        return is_college(self.exam) or is_school(self.exam) or is_placement(self.exam)

    @property
    def tests(self) -> bool:
        """Takes timed tests at all (school: only the board years, Classes 10 and 12)."""
        return has_tests(self.exam)

    @property
    def kind(self) -> str:
        return {"college": "college", "gate": "gate", "cbse": "school", "placement": "gate", "ssc_cgl": "gate"}.get(group(self.exam) or "", "entrance")


@dataclass
class Progress:
    done_topics: dict[str, date] = field(default_factory=dict)        # topic id → day finished
    revisions: dict[str, list[date]] = field(default_factory=dict)   # chapter id → days revised
    checks: set[str] = field(default_factory=set)                    # today's ticked task keys ("hide:<key>": not today)
    focus_minutes_week: int | None = None                            # focus time in the last 7 days
    custom: list[dict[str, Any]] = field(default_factory=list)       # the student's own tasks for today
    weak: list[dict[str, Any]] = field(default_factory=list)         # weak spots from tests, most questions lost first


# ---------------------------------------------------------------- standing → ticks (onboarding)
def topics_from_standing(syl: Syllabus, standing: dict[str, dict[str, str]]) -> list[str]:
    """Topics to mark done for what a student says they've already covered: everything for "done", the first
    half of each chapter for "partial". They can adjust any of it in the Prep Hub."""
    out: list[str] = []
    for ch in syl.chapters:
        said = standing.get(ch.subject) or {}
        level = said.get(str(ch.cls)) or said.get("all") or "none"  # college: one answer for the whole course
        if level == "done":
            out += [t.id for t in ch.topics]
        elif level == "partial":
            out += [t.id for t in ch.topics[: len(ch.topics) // 2]]
    return out


# ---------------------------------------------------------------- helpers
def _done_fraction(ch: Chapter, progress: Progress) -> float:
    return sum(t.id in progress.done_topics for t in ch.topics) / max(1, len(ch.topics))


def _finished_on(ch: Chapter, progress: Progress) -> date | None:
    days = [progress.done_topics.get(t.id) for t in ch.topics]
    return max(days) if days and all(days) else None  # type: ignore[type-var]


def revision_window(today: date, exam_date: date, college: bool = False) -> int:
    """Days of pure revision before the exam: 4-12 weeks with time in hand, less in a crunch, but always the last
    two days. Nobody should be starting a chapter the day before. A semester's exams get one to two weeks."""
    days = (exam_date - today).days
    least, most = (7, 14) if college else (28, 84)
    return max(min(2, days), int(min(max(least, days * 0.15), most, days * 0.4)))


def _order(chapters: list[Chapter], class_level: str, priority: bool = False, college: bool = False) -> list[Chapter]:
    index = {c.id: i for i, c in enumerate(chapters)}
    if priority:  # not enough time for everything: foundations, then the most marks per hour of study
        return sorted(chapters, key=lambda c: (not c.foundation, -c.weight / c.hours, index[c.id]))
    if college or class_level.isdigit() and int(class_level) <= 10:  # a course, or a school class: in the order it is taught
        return list(chapters)
    if class_level == "11":
        return sorted(chapters, key=lambda c: (c.cls, index[c.id]))
    if class_level == "12":
        twelve = [c for c in chapters if c.cls == 12]
        backlog = sorted((c for c in chapters if c.cls == 11), key=lambda c: (not c.foundation, -c.weight / c.hours, index[c.id]))
        out = []
        for i in range(max(len(twelve), len(backlog))):  # school chapters alongside the Class 11 backlog
            out += twelve[i:i + 1] + backlog[i:i + 1]
        return out
    return sorted(chapters, key=lambda c: (not c.foundation, -c.weight / c.hours if not c.foundation else index[c.id]))


def _queue(chapters: list[Chapter], goal: Goal, priority: bool = False) -> list[Chapter]:
    """The order a subject's chapters are studied in: the mentor's order, minus the chapters the student left
    out, with the ones they asked for next moved to the front."""
    ordered = [c for c in _order(chapters, goal.class_level, priority, goal.college) if c.id not in goal.skipped]
    rank = {cid: i for i, cid in enumerate(goal.pinned)}
    return sorted(ordered, key=lambda c: rank.get(c.id, len(rank)))  # stable: everything unpinned keeps its place


def _week_end(day: date) -> date:
    return day + timedelta(days=6 - day.weekday())


def _remaining_topics(ch: Chapter, progress: Progress) -> list:
    return [t for t in ch.topics if t.id not in progress.done_topics]


def _qph(exam: str, subject: str) -> int:
    if exam == "ssc_cgl":
        return 30  # SSC questions are a minute or less each
    return (NEET_QPH if exam == "neet" else QUESTIONS_PER_HOUR).get(subject, 10)


# ---------------------------------------------------------------- the plan
def build(goal: Goal, syl: Syllabus, progress: Progress, today: date, baseline: list | None = None) -> dict[str, Any]:
    days_left = (goal.exam_date - today).days
    total_hours = syl.total_hours
    frac = {c.id: _done_fraction(c, progress) for c in syl.chapters}
    remaining = {c.id: c.hours * (1 - frac[c.id]) for c in syl.chapters}
    done_hours = total_hours - sum(remaining.values())
    by_subject = {s: round(100 * sum(c.hours * frac[c.id] for c in syl.subject_chapters(s))
                           / max(1e-9, sum(c.hours for c in syl.subject_chapters(s))), 1) for s in syl.subjects}
    completion = round(100 * done_hours / total_hours, 1)
    target = target_info(goal.exam, goal.target)

    if days_left <= 0:  # nothing left to plan, but the pages that show a plan still get every field they read
        return {"status": "past", "exam_date": goal.exam_date.isoformat(), "days_left": days_left, "completion": completion,
                "by_subject": by_subject, "mentor": [{"tone": "info", "title": "Your exam date has passed",
                                                      "text": "Set the date of your next attempt (Edit plan) to get a new plan."}],
                "months": [], "weeks": [], "today": None, "baseline": [], "target": target, "expected_now": None,
                "revision_from": goal.exam_date.isoformat(), "revision_weeks": 0, "syllabus_done_on": None,
                "hours": {"weekday": goal.weekday_hours, "weekend": goal.weekend_hours, "weekly": round(goal.weekly_hours, 1),
                          "by_day": list(goal.by_day), "custom_days": goal.day_hours is not None, "needed_daily": 0},
                "unfinished": [], "priority_mode": False, "covered_weight": 0, "skipped": [], "skipped_weight": 0, "pinned": [],
                "kind": goal.kind, "subject_tests": goal.subject_tests}

    rw = revision_window(today, goal.exam_date, goal.college)
    learn_end = goal.exam_date - timedelta(days=rw)
    test_hours = SUBJECT_TEST_HOURS if goal.subject_tests else MOCK_HOURS
    skipped = [c for c in syl.chapters if c.id in goal.skipped and remaining[c.id] > 1e-6]  # left out by the student
    need = sum(h for cid, h in remaining.items() if cid not in goal.skipped)
    # reordering by marks is for a crunch: a Class 11 student with time ahead keeps the school order
    priority = (goal.college or goal.class_level != "11" or days_left < 240) and needs_priority(goal, need, today, learn_end)
    queues = {s: [c for c in _queue(syl.subject_chapters(s), goal, priority) if remaining[c.id] > 1e-6]
              for s in syl.subjects}
    # ---- the simulation: week by week until the exam
    weeks: list[dict[str, Any]] = []
    planned_finish: dict[str, date] = {}
    left = dict(remaining)
    consumed = {c.id: 0.0 for c in syl.chapters}
    cum_hours = done_hours
    baseline_out: list[list] = [[today.isoformat(), completion]]  # where the student starts
    day = today
    syllabus_done_on: date | None = None if any(queues.values()) else today
    while day < goal.exam_date:
        end = min(_week_end(day), goal.exam_date - timedelta(days=1))
        days = [day + timedelta(days=i) for i in range((end - day).days + 1)]
        cap = sum(goal.hours_on(d) for d in days)
        in_revision = day >= learn_end
        learn_cap = cap * (LEARN_SHARE if not in_revision else 0.5 if any(queues.values()) else 0)
        items: list[dict[str, Any]] = []
        finished: list[str] = []
        rem_by_subject = {s: sum(left[c.id] for c in q) for s, q in queues.items()}
        pool = sum(rem_by_subject.values())
        for s, q in queues.items():
            budget = learn_cap * rem_by_subject[s] / pool if pool > 0 else 0
            while budget > 1e-6 and q:
                ch = q[0]
                take = min(budget, left[ch.id])
                todo = _remaining_topics(ch, progress)
                th = remaining[ch.id] / max(1, len(todo))
                a = int(consumed[ch.id] / th) if th else 0
                consumed[ch.id] += take
                b = min(len(todo), max(a + 1, math.ceil(consumed[ch.id] / th - 1e-9))) if th else a
                left[ch.id] -= take
                budget -= take
                items.append({"chapter_id": ch.id, "chapter": ch.name, "subject": s, "hours": round(take, 1),
                              "topics": [t.name for t in todo[a:b]], "finishes": left[ch.id] <= 1e-6})
                if left[ch.id] <= 1e-6:
                    planned_finish[ch.id] = end
                    finished.append(ch.id)
                    q.pop(0)
        cum_hours += sum(i["hours"] for i in items)
        pct = round(100 * cum_hours / total_hours, 1)
        if syllabus_done_on is None and not any(queues.values()):
            syllabus_done_on = end
        weeks_to_exam = (goal.exam_date - end).days / 7
        if not goal.tests:
            mocks = 0
        elif in_revision:
            mocks = max(1, int(cap * 0.45 / test_hours)) if cap >= test_hours else 0
        elif pct >= 30 and cap * TEST_SHARE >= test_hours / 2:
            mocks = 1 if weeks_to_exam <= 26 or len(weeks) % 2 == 0 else 0
        else:
            mocks = 0
        revise = [{"id": c.id, "name": c.name} for c in syl.chapters
                  if (base := planned_finish.get(c.id) or _finished_on(c, progress)) is not None
                  and any(day <= base + timedelta(days=k) <= end for k in SPACED_DAYS)]
        tests = [{"id": cid, "name": syl.by_id[cid].name} for cid in (weeks[-1]["finished"] if weeks and goal.tests else [])]
        weeks.append({"start": day.isoformat(), "end": end.isoformat(), "phase": "revision" if in_revision else "learning",
                      "hours": round(cap, 1), "learn": items, "finished": finished, "revise": revise[:12],
                      "chapter_tests": tests, "mocks": mocks, "completion": pct,
                      "questions": int(sum(i["hours"] * 0.4 * _qph(goal.exam, i["subject"]) for i in items))})
        baseline_out.append([end.isoformat(), pct])
        day = end + timedelta(days=1)

    unfinished = [c.name for q in queues.values() for c in q]
    learn_weeks_cap = sum(w["hours"] for w in weeks if w["phase"] == "learning") * LEARN_SHARE
    not_covered = set(unfinished) | {c.name for c in skipped}
    ratio = need / learn_weeks_cap if learn_weeks_cap else math.inf
    status = ("done" if need <= 1e-6 else "comfortable" if ratio <= 0.85 else "on_track" if ratio <= 1.0
              else "tight" if not unfinished else "behind")

    expected_now = _expected(baseline, today)
    plan = {
        "status": status, "exam_date": goal.exam_date.isoformat(), "days_left": days_left,
        "revision_from": learn_end.isoformat(), "revision_weeks": round(rw / 7),
        "syllabus_done_on": syllabus_done_on.isoformat() if syllabus_done_on else None,
        "completion": completion, "by_subject": by_subject, "expected_now": expected_now,
        "hours": {"weekday": goal.weekday_hours, "weekend": goal.weekend_hours, "weekly": round(goal.weekly_hours, 1),
                  "by_day": list(goal.by_day), "custom_days": goal.day_hours is not None,
                  "needed_daily": _needed_daily(need, weeks, learn_end)},
        "target": target, "unfinished": unfinished, "priority_mode": priority,
        "covered_weight": round(100 * sum(c.weight for c in syl.chapters if c.name not in not_covered)
                                / sum(c.weight for c in syl.chapters)),
        "skipped": [{"id": c.id, "name": c.name, "subject": c.subject, "weightage": weight_label(c.weight)} for c in skipped],
        "skipped_weight": round(100 * sum(c.weight for c in skipped) / sum(c.weight for c in syl.chapters)),
        "pinned": [cid for cid in goal.pinned if cid in syl.by_id and remaining[cid] > 1e-6 and cid not in goal.skipped],
        "weeks": weeks, "months": _months(weeks, syl, planned_finish, learn_end, all_done=not unfinished and not skipped, subject_tests=goal.subject_tests),
        "kind": goal.kind, "subject_tests": goal.subject_tests,
        "baseline": baseline_out,
    }
    plan["mentor"] = _mentor(goal, syl, progress, plan, today, ratio)
    plan["today"] = today_plan(goal, syl, progress, today, learn_end, weeks[0] if weeks else None, priority)
    return plan


def clean_edits(syl: Syllabus, edits: dict | None) -> tuple[tuple[float, ...] | None, tuple[str, ...], frozenset[str]]:
    """A goal's stored edits → (day_hours, pinned, skipped), dropping anything that no longer fits the syllabus."""
    edits = edits or {}
    hours = edits.get("day_hours")
    day_hours = tuple(float(h) for h in hours) if isinstance(hours, list) and len(hours) == 7 else None
    skipped = frozenset(c for c in edits.get("skipped") or [] if c in syl.by_id)
    pinned = tuple(dict.fromkeys(c for c in edits.get("pinned") or [] if c in syl.by_id and c not in skipped))
    return day_hours, pinned, skipped


def _capacity(goal: Goal, start: date, end: date) -> float:
    return sum(goal.hours_on(start + timedelta(days=i)) for i in range(max(0, (end - start).days)))


def needs_priority(goal: Goal, need: float, today: date, learn_end: date) -> bool:
    """True when the remaining chapters can't all fit before the exam, even using half the revision window."""
    learning = _capacity(goal, today, learn_end) * LEARN_SHARE + _capacity(goal, learn_end, goal.exam_date) * 0.5
    return need > learning


def _expected(baseline: list | None, today: date) -> float | None:
    if not baseline:
        return None
    iso = today.isoformat()
    prev = None
    for d, pct in baseline:
        if d >= iso:
            return pct if prev is None else round(prev[1] + (pct - prev[1]) * _between(prev[0], d, iso), 1)
        prev = (d, pct)
    return baseline[-1][1]


def _between(a: str, b: str, x: str) -> float:
    da, db, dx = date.fromisoformat(a), date.fromisoformat(b), date.fromisoformat(x)
    return (dx - da).days / max(1, (db - da).days)


def _needed_daily(need: float, weeks: list, learn_end: date) -> float:
    learning_days = sum((date.fromisoformat(w["end"]) - date.fromisoformat(w["start"])).days + 1
                        for w in weeks if w["phase"] == "learning")
    return round(need / LEARN_SHARE / max(1, learning_days), 1)


def _months(weeks: list, syl: Syllabus, planned_finish: dict[str, date], learn_end: date, all_done: bool,
            subject_tests: bool = False) -> list[dict]:
    months: dict[str, dict[str, Any]] = {}
    for w in weeks:
        key = w["start"][:7]
        m = months.setdefault(key, {"month": key, "phase": w["phase"], "hours": 0.0, "mocks": 0, "finish": [], "start": [],
                                    "questions": 0, "milestones": [], "completion": 0})
        m["hours"] += w["hours"]
        m["mocks"] += w["mocks"]
        m["questions"] += w["questions"]
        m["completion"] = w["completion"]
        if w["phase"] == "revision":
            m["phase"] = "revision" if m["phase"] == "revision" or not m["finish"] else "mixed"
        for item in w["learn"]:
            entry = {"id": item["chapter_id"], "name": item["chapter"], "subject": item["subject"]}
            if item["finishes"]:
                m["finish"].append(entry)
            elif all(e["id"] != item["chapter_id"] for e in m["start"] + m["finish"]):
                m["start"].append(entry)
    # milestones: each subject's Class 11 part (college: each subject) and the whole syllabus
    for s in syl.subjects:
        for cls in (None,) if syl.is_college else (11, 12):
            ids = [c.id for c in syl.subject_chapters(s) if cls is None or c.cls == cls]
            if ids and all(i in planned_finish for i in ids):
                when = max(planned_finish[i] for i in ids).isoformat()[:7]
                if when in months:
                    months[when]["milestones"].append(f"{s} complete" if cls is None else f"Class {cls} {s} complete")
    if planned_finish and all_done:
        last = max(planned_finish.values()).isoformat()[:7]
        if last in months:
            months[last]["milestones"].append("All subjects covered" if syl.is_college else "Whole syllabus done")
    rev = learn_end.isoformat()[:7]
    if rev in months:
        months[rev]["milestones"].append("Revision and subject tests begin" if subject_tests else "Full revision and mocks begin")
    for m in months.values():
        m["hours"] = round(m["hours"])
    return list(months.values())


def _mentor(goal: Goal, syl: Syllabus, progress: Progress, plan: dict, today: date, ratio: float) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    avg = goal.weekly_hours / 7
    done_on = plan["syllabus_done_on"]
    revision_weeks = plan["revision_weeks"]
    college = goal.college
    finished = date.fromisoformat(done_on) if done_on else None
    when = (finished.strftime("%d %B").lstrip("0") if college else finished.strftime("%B %Y")) if finished else None
    tests = "subject tests" if goal.subject_tests else "full mocks"
    exam = "your exams" if college else "the exam"
    window = f"{revision_weeks} week{'' if revision_weeks == 1 else 's'}"
    status = plan["status"]
    if status == "done":
        out.append({"tone": "good", "title": "Syllabus covered",
                    "text": f"Everything is marked done. Your plan is now revision, {'past papers' if college else 'PYQs'} "
                            f"and {tests} until {exam}."})
    elif status in ("comfortable", "on_track"):
        spare = "with time to spare" if status == "comfortable" else "right on time"
        out.append({"tone": "good", "title": "This plan works",
                    "text": f"At {avg:.1f} h a day you finish the syllabus by {when}, {spare}, then get "
                            f"{window} of revision and {tests} before {exam}."})
    elif status == "tight":
        out.append({"tone": "warn", "title": "Tight, but doable",
                    "text": f"Your syllabus finishes by {when}, cutting into the {revision_weeks}-week revision window. "
                            f"About {plan['hours']['needed_daily']:.1f} h a day keeps the full revision time."})
    else:
        needed = plan["hours"]["needed_daily"]
        more = (f"Covering everything would take about {needed:.1f} h a day. " if needed <= 14 else
                "Covering everything isn't realistic in the time left, and that's fine: ")
        out.append({"tone": "warn", "title": "Priority mode: most marks first",
                    "text": f"At {avg:.1f} h a day, {len(plan['unfinished'])} chapters won't fit before {exam}. {more}"
                            f"Your plan takes chapters by marks per hour of study, so what you cover is worth about "
                            f"{plan['covered_weight']}% of the {'marks' if college else 'paper'}. The rest wait at the end in case you get time."})
    if plan["skipped"]:
        n = len(plan["skipped"])
        out.append({"tone": "warn" if plan["skipped_weight"] >= 15 else "info",
                    "title": f"{n} chapter{'s' if n != 1 else ''} left out of your plan",
                    "text": f"You chose to leave {'them' if n != 1 else 'it'} out: about {plan['skipped_weight']}% of the {'marks' if college else 'paper'}. "
                            "The time goes to everything else. Bring a chapter back any time, at the end of this page."})
    t = plan["target"]
    if avg + 0.5 < t["hours"]:
        out.append({"tone": "info", "title": f"For {t['label']}",
                    "text": (f"Students who get this usually study about {t['hours']:g} h a day outside classes. You've planned "
                             f"{avg:.1f}. Even {_more_hours(t['hours'] - avg)} a day adds up over a semester. (A rule of "
                             "thumb: grading differs from course to course.)") if college else
                            (f"Students who reach this usually study about {t['hours']} h a day, classes included. "
                             f"You've planned {avg:.1f}. Even {_more_hours(t['hours'] - avg)} a day makes a real "
                             "difference over months. (A rule of thumb: cut-offs move every year.)")})
    else:
        out.append({"tone": "good", "title": f"Hours match {t['label']}",
                    "text": "Your planned hours are what this goal usually takes. Consistency now matters more than more hours."})
    expected = plan["expected_now"]
    if expected is not None:
        gap = plan["completion"] - expected
        per_day = max(1e-9, 100 * goal.weekly_hours * LEARN_SHARE / 7 / syl.total_hours)
        days = round(abs(gap) / per_day)
        if gap < 0 and days >= 3:
            out.append({"tone": "warn", "title": f"About {days} days behind your plan",
                        "text": "The rest of the plan has been reshuffled to absorb it. Thirty extra minutes a day "
                                f"for {max(1, math.ceil(days * avg * 2 / 7))} weeks brings you back on schedule."})
        elif gap > 0 and days >= 3:
            out.append({"tone": "good", "title": f"{days} days ahead of your plan",
                        "text": f"Nicely done. Use the spare time for extra {'past-paper questions' if college else 'PYQs'} on your weakest chapters."})
    subj = plan["by_subject"]
    if len(subj) > 1 and max(subj.values()) - min(subj.values()) >= 15 and plan["completion"] < 95:
        low = min(subj, key=subj.get)
        out.append({"tone": "info", "title": f"{low} is behind the others",
                    "text": f"{low} is at {subj[low]:.0f}% while your best subject is at {max(subj.values()):.0f}%. "
                            "Your weekly plan gives it more time until they're level."})
    debt = [c for c in syl.chapters if (f := _finished_on(c, progress)) and (today - f).days >= 7
            and not progress.revisions.get(c.id)]
    if debt:
        out.append({"tone": "info", "title": f"{len(debt)} finished chapter{'s' if len(debt) != 1 else ''} not revised yet",
                    "text": "Revision is what makes chapters stick. They're in your daily plan, one at a time."})
    still_weak = [w for w in progress.weak if not w["cleared"]]
    if still_weak:
        n = len(still_weak)
        out.append({"tone": "warn", "title": f"{n} weak spot{'s' if n != 1 else ''} from your tests",
                    "text": "Each day's list starts with one of them, the costliest first: read its notes, practise it, "
                            "and a re-check of 70% or better clears it. They also move up your last-day revision."})
    if progress.focus_minutes_week is not None:
        planned = goal.weekly_hours * 60
        got = progress.focus_minutes_week
        if planned and got < planned * 0.6:
            out.append({"tone": "warn", "title": "Last 7 days",
                        "text": f"Focus time was {got / 60:.1f} h of the {planned / 60:.0f} h planned. If your plan "
                                "is too heavy, lower your hours in your goal: a plan you follow beats a perfect one."})
    if goal.exam == "jee" and goal.exam_date.month == 4:
        out.append({"tone": "info", "title": "Aiming at session 2 (April)",
                    "text": "Session 1 in January comes before your syllabus is done, so treat it as a full-length "
                            "rehearsal: same timing, same seriousness, then learn from the result."})
    if goal.track == "jee_advanced":
        out.append({"tone": "info", "title": "JEE Advanced",
                    "text": "The plan finishes the syllabus before JEE Main. From then until Advanced (late May), the focus "
                            "moves to Advanced-level problems and full Advanced papers."})
    return out


def _more_hours(diff: float) -> str:
    h = max(0.5, min(2.0, round(diff * 2) / 2))
    return f"{h:g} more hour{'s' if h > 1 else ''}"


# ---------------------------------------------------------------- today
KIND_LABEL = {"learn": "Learn", "practice": "Practise", "revise": "Revise", "test": "Test", "mock": "Mock", "fix": "Fix"}
FIX_MINUTES = 30  # a day, on the weak spot that cost the most marks


def _due_revision(syl: Syllabus, progress: Progress, today: date) -> Chapter | None:
    """The most overdue finished chapter on the 7 / 30 / 90-day revision schedule."""
    best, best_late = None, -1
    for c in syl.chapters:
        finished = _finished_on(c, progress)
        if not finished:
            continue
        revs = sorted(progress.revisions.get(c.id, []))
        if any(r == today for r in revs):
            return c
        step = len(revs)
        if step >= len(SPACED_DAYS):
            continue
        due = (revs[-1] if revs else finished) + timedelta(days=SPACED_DAYS[step] - (SPACED_DAYS[step - 1] if step else 0))
        late = (today - due).days
        if late >= 0 and late > best_late:
            best, best_late = c, late
    return best


def today_plan(goal: Goal, syl: Syllabus, progress: Progress, today: date, learn_end: date,
               week: dict | None, priority: bool = False) -> dict[str, Any]:
    hours = goal.hours_on(today)
    own = [{"key": f"custom:{c['id']}", "kind": "custom", "title": c["title"], "minutes": c["minutes"], "done": c["done"]}
           for c in progress.custom]
    if hours <= 0:
        return {"date": today.isoformat(), "minutes": 0, "tasks": own, "done": sum(t["done"] for t in own), "hidden": [],
                "note": None if own else "Rest day in your plan. Recharge."}
    minutes = int(hours * 60)
    tasks: list[dict[str, Any]] = []
    in_revision = today >= learn_end
    # the day's list is built from progress as it was this morning, so ticking a task keeps it (done) in the list
    # instead of swapping in the next topic; what was ticked today shows as done
    morning = Progress(done_topics={t: d for t, d in progress.done_topics.items() if d < today},
                       revisions=progress.revisions, checks=progress.checks)
    queues = {s: [c for c in _queue(syl.subject_chapters(s), goal, priority) if _done_fraction(c, morning) < 1]
              for s in syl.subjects}  # same order as the week plan, so today and this week always agree
    cycle = _cycle(goal.exam, syl.subjects)
    asked = [syl.by_id[c].subject for c in goal.pinned if c in syl.by_id]  # "take this next" means today, not on its turn
    subjects = [s for s in dict.fromkeys([*asked, *cycle[today.toordinal() % len(cycle)]]) if queues.get(s)][:2]
    subjects += [s for s in syl.subjects if queues.get(s) and s not in subjects][: max(0, 2 - len(subjects))]

    if not in_revision and subjects:
        learn_min, practice_min = minutes * 0.5, minutes * 0.3
        for s in subjects:
            ch = queues[s][0]
            todo = _remaining_topics(ch, morning)
            share = learn_min / len(subjects)
            n = max(1, min(len(todo), round(share / (ch.topic_hours * 60))))
            topics = todo[:n]
            tasks.append({"key": f"learn:{topics[0].id}", "kind": "learn", "subject": s, "chapter_id": ch.id,
                          "chapter": ch.name, "minutes": int(share),
                          "title": topics[0].name if n == 1 else f"{topics[0].name} + {n - 1} more",
                          "topics": [{"id": t.id, "name": t.name} for t in topics],
                          "done": all(t.id in progress.done_topics for t in topics)})
        main = queues[subjects[0]][0]
        q = max(5, int(practice_min / 60 * _qph(goal.exam, main.subject)) // 5 * 5)
        tasks.append({"key": f"practice:{main.id}", "kind": "practice", "subject": main.subject, "chapter_id": main.id,
                      "chapter": main.name, "minutes": int(practice_min), "questions": q,
                      "title": f"Solve {q} questions", "done": f"practice:{main.id}" in progress.checks})
    elif in_revision:
        mock_day = today.weekday() in (2, 6) and goal.tests  # Wednesday and Sunday
        if mock_day and goal.subject_tests:
            tasks.append({"key": "mock", "kind": "mock", "minutes": int(SUBJECT_TEST_HOURS * 60), "title": "Subject test + analysis",
                          "done": "mock" in progress.checks})
        elif mock_day:
            tasks.append({"key": "mock", "kind": "mock", "minutes": 180 + 90, "title": "Full mock test + analysis",
                          "done": "mock" in progress.checks})
    revise = _due_revision(syl, progress, today)
    if revise is None and in_revision:
        # final revision: the chapter revised longest ago
        finished = [c for c in syl.chapters if _done_fraction(c, progress) >= 1]
        revise = min(finished, key=lambda c: max(progress.revisions.get(c.id, [date.min])), default=None)
    if revise is not None:
        rmin = int(minutes * (0.2 if not in_revision else 0.5))
        tasks.append({"key": f"revise:{revise.id}", "kind": "revise", "subject": revise.subject, "chapter_id": revise.id,
                      "chapter": revise.name, "minutes": rmin, "title": revise.name,
                      "done": today in progress.revisions.get(revise.id, [])})
    if week and week.get("chapter_tests") and today.weekday() == 5:  # Saturday: test what you finished last week
        cid = week["chapter_tests"][0]["id"]
        ch = syl.by_id.get(cid)
        if ch:
            tasks.append({"key": f"test:{cid}", "kind": "test", "subject": ch.subject, "chapter_id": cid, "chapter": ch.name,
                          "minutes": 45, "title": ch.name, "done": f"test:{cid}" in progress.checks})
    # one weak spot a day, first on the list: read its notes, practise it, and the re-check clears it
    if progress.weak:
        w = progress.weak[0]
        name = w["topic"]["name"] if w["topic"] else w["chapter"]
        tasks.insert(0, {"key": f"fix:{w['id']}", "kind": "fix", "subject": w["subject"], "chapter_id": w["chapter_id"],
                         "chapter": w["chapter"], "minutes": FIX_MINUTES, "title": name, "weak_id": w["id"],
                         "topics": [w["topic"]] if w["topic"] else [], "more": len(progress.weak) - 1,
                         "done": w["cleared"] or f"fix:{w['id']}" in progress.checks})
    # the student's edits to today's list: planned tasks they don't want today, and tasks of their own
    not_today = {c[5:] for c in progress.checks if c.startswith("hide:")}
    hidden = [{"key": t["key"], "title": f"{KIND_LABEL[t['kind']]}: {t['title']}"} for t in tasks if t["key"] in not_today]
    planned = bool(tasks)
    tasks = [t for t in tasks if t["key"] not in not_today] + own
    done = sum(t["done"] for t in tasks)
    note = None if tasks else ("You've taken everything off today's list." if planned else
                               "Everything for today is covered. Revise a weak chapter or take a chapter test.")
    return {"date": today.isoformat(), "minutes": minutes, "tasks": tasks, "done": done, "hidden": hidden, "note": note}


def chapter_summary(ch: Chapter, progress: Progress) -> dict[str, Any]:
    finished = _finished_on(ch, progress)
    return {"id": ch.id, "name": ch.name, "subject": ch.subject, "unit": ch.unit, "class": ch.cls, "hours": ch.hours,
            "weight": ch.weight, "weightage": weight_label(ch.weight), "foundation": ch.foundation,
            "done": sum(t.id in progress.done_topics for t in ch.topics), "total": len(ch.topics),
            "finished_on": finished.isoformat() if finished else None,
            "revisions": len(progress.revisions.get(ch.id, []))}
