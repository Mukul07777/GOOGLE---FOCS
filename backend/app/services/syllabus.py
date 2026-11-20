"""What a student studies: subjects → units → chapters → topics.

Two kinds of syllabus, read from app/data/syllabus:

* Entrance exams (``jee.json``, ``neet.json``): one fixed syllabus per exam. A chapter carries its class (11/12).
* College (``college/``): a library of B.Tech courses (a course is a subject, its units are the chapters) and, per
  branch, the plan of which courses fall in which semester: a typical one, and a college's own where its scheme was
  checked. A chapter carries the semester its course is planned in. A college student works on *their* subjects
  (this semester's, or the list they picked), which is what ``of`` returns; the whole library stays reachable so
  a topic of any course can be opened.
* School (``school/class_NN.json``, Classes 1-12): each class's subjects by NCERT book, chapter by chapter as the
  books' contents pages list them; Classes 9-12 follow the CBSE curriculum of the year (its marks per unit, and
  without the chapters CBSE dropped). Chapter IDs carry the class ("c11.physics.units-and-measurements").

Every chapter carries an approximate weightage and the self-study hours it takes to learn and practise. A topic may
be a plain name or {"name", "video", "notes"} once lectures and notes are added for it. IDs are stable slugs
("physics.kinematics", "data-structures.trees.avl-trees-and-rotations"): progress is stored against them, so
renaming a topic in the JSON starts its progress afresh.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache, cached_property, lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data" / "syllabus"
COLLEGE = DATA / "college"
SCHOOL_DIR = DATA / "school"
ENTRANCE = ("jee", "neet", "ssc_cgl")
# exams that are not studied by class: a chapter's "class" is 0
GOVT = ("ssc_cgl",)
SEMESTERS = tuple(range(1, 9))
COURSE_UNIT = "Course syllabus"  # a course has no layer between itself and its chapters


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", " and ")).strip("-")


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    video: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class Chapter:
    id: str
    subject: str
    unit: str
    name: str
    cls: int          # class 11/12; for a college course the semester it is planned in (0: not in this plan)
    hours: float
    weight: float
    foundation: bool
    topics: tuple[Topic, ...]

    @property
    def topic_hours(self) -> float:
        return self.hours / max(1, len(self.topics))


@dataclass(frozen=True)
class Syllabus:
    exam: str
    name: str
    about: str
    subjects: tuple[str, ...]
    units: tuple[tuple[str, str], ...]  # (subject, unit) in order
    chapters: tuple[Chapter, ...]
    kind: str = "entrance"              # entrance | college
    library: str = ""                   # whose notes and questions these are: jee | neet | college
    college: str | None = None          # college syllabus: whose semester plan this is ("other": the typical one)
    semesters: tuple[tuple[int, tuple[str, ...]], ...] = ()  # college: semester → its courses
    source: str = ""                    # college: where the semester plan comes from

    @cached_property
    def by_id(self) -> dict[str, Chapter]:
        return {c.id: c for c in self.chapters}

    @cached_property
    def _by_subject(self) -> dict[str, list[Chapter]]:
        out: dict[str, list[Chapter]] = {s: [] for s in self.subjects}
        for c in self.chapters:
            out[c.subject].append(c)
        return out

    def topic(self, topic_id: str) -> tuple[Chapter, Topic] | None:
        chapter_id = topic_id.rsplit(".", 1)[0]
        chapter = self.by_id.get(chapter_id)
        if chapter is None:
            return None
        return next(((chapter, t) for t in chapter.topics if t.id == topic_id), None)

    def has_subject(self, subject: str) -> bool:
        return subject in self._by_subject

    def subject_chapters(self, subject: str) -> list[Chapter]:
        return list(self._by_subject.get(subject, ()))

    @cached_property
    def total_hours(self) -> float:
        return sum(c.hours for c in self.chapters)

    @property
    def is_college(self) -> bool:
        return self.kind == "college"

    def semester_subjects(self, semester: int) -> tuple[str, ...]:
        return next((subjects for n, subjects in self.semesters if n == semester), ())

    def semester_of(self, subject: str) -> int:
        return next((n for n, subjects in self.semesters if subject in subjects), 0)

    def only(self, subjects: tuple[str, ...] | list[str]) -> Syllabus:
        """The same syllabus cut down to some of its subjects, in the order given."""
        keep = tuple(dict.fromkeys(s for s in subjects if s in self._by_subject))
        chosen = set(keep)
        return Syllabus(exam=self.exam, name=self.name, about=self.about, subjects=keep,
                        units=tuple(u for s in keep for u in self.units if u[0] == s),
                        chapters=tuple(c for s in keep for c in self._by_subject[s]), kind=self.kind, library=self.library,
                        college=self.college, semesters=tuple((n, tuple(s for s in ss if s in chosen)) for n, ss in self.semesters),
                        source=self.source)


def _topic(chapter_id: str, raw: Any) -> Topic:
    if isinstance(raw, str):
        return Topic(f"{chapter_id}.{slug(raw)}", raw)
    return Topic(f"{chapter_id}.{slug(raw['name'])}", raw["name"], raw.get("video"), raw.get("notes"))


def _subject(raw: dict, *, hours_factor: float = 1.0, weights: dict[str, float] | None = None) -> tuple[list, list]:
    name = raw["name"]
    units, chapters = [], []
    for unit in raw["units"]:
        units.append((name, unit["name"]))
        for c in unit["chapters"]:
            cid = f"{slug(name)}.{slug(c['name'])}"
            chapters.append(Chapter(
                id=cid, subject=name, unit=unit["name"], name=c["name"], cls=int(c["class"]),
                hours=round(float(c["hours"]) * hours_factor, 1), weight=float((weights or {}).get(c["name"], c["weight"])),
                foundation=bool(c.get("foundation")), topics=tuple(_topic(cid, t) for t in c["topics"]),
            ))
    return units, chapters


def _raw(exam: str) -> dict:
    return json.loads((DATA / f"{exam}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- college: the course library and semester plans
@cache
def courses() -> dict[str, dict]:
    """Every course in the library, by name, in file order: {"name", "about", "area", "chapters": [...]}."""
    out: dict[str, dict] = {}
    for path in sorted(COLLEGE.glob("*.json")):
        if path.name == "branches.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for course in data["courses"]:
            if course["name"] in out:
                raise ValueError(f"course {course['name']!r} is in the library twice")
            out[course["name"]] = {**course, "area": data["area"]}
    return out


@cache
def _plans() -> dict:
    return json.loads((COLLEGE / "branches.json").read_text(encoding="utf-8"))


BRANCHES: dict[str, dict[str, str]] = {b["id"]: b for b in _plans()["branches"]}
COLLEGE_BRANCHES = tuple(BRANCHES)
COLLEGES: dict[str, dict[str, str]] = {c["id"]: c for c in _plans()["colleges"]}
# GATE: a paper is a set of library courses, each worth roughly so many of the paper's 100 marks
PAPERS: dict[str, dict] = {p["id"]: p for p in json.loads((DATA / "gate.json").read_text(encoding="utf-8"))["papers"]}
# School: Classes 1-12 (CBSE, NCERT books)
SCHOOL = {f"cbse_{n}": n for n in range(1, 13)}
# self-study hours of an average chapter, by class (a heavier chapter takes longer)
SCHOOL_HOURS = {1: 2.5, 2: 2.5, 3: 3, 4: 3, 5: 3, 6: 5, 7: 5, 8: 5, 9: 7, 10: 7, 11: 9, 12: 9}
# placements (software roles): library courses too, each with a share of what the rounds test
PLACEMENT = "placement"
EXAMS = (*ENTRANCE, *COLLEGE_BRANCHES, *PAPERS, *SCHOOL, PLACEMENT)
# targets from before an exam had papers, branches or classes of its own
EXAM_OF_TARGET = {"college": "college_cse", "gate": "gate_cs", "cbse": "cbse_12", "coding": PLACEMENT}


def is_college(exam: str | None) -> bool:
    return exam in BRANCHES


def is_gate(exam: str | None) -> bool:
    return exam in PAPERS


def is_school(exam: str | None) -> bool:
    return exam in SCHOOL


def is_placement(exam: str | None) -> bool:
    return exam == PLACEMENT


def group(exam: str | None) -> str | None:
    """The kind of exam a syllabus is for, which decides its goals, dates and wording: jee | neet | college | gate |
    cbse | placement."""
    return ("college" if is_college(exam) else "gate" if is_gate(exam) else "cbse" if is_school(exam)
            else exam if exam in ENTRANCE or exam == PLACEMENT else None)


def family(exam: str | None) -> str | None:
    """Whose notes library and question bank a syllabus draws on: every branch and GATE paper shares the college
    one (they are the same courses), the two school classes share one."""
    courses_ = is_college(exam) or is_gate(exam) or is_placement(exam)
    return "college" if courses_ else "cbse" if is_school(exam) else exam if exam in ENTRANCE else None


def college_of(value: str | None) -> str:
    return value if value in COLLEGES else "other"


def has_own_plan(exam: str, college: str | None) -> bool:
    return college_of(college) != "other" and college_of(college) in _plans()["layouts"][exam]


@cache
def semester_plan(exam: str, college: str | None = None) -> tuple[tuple[tuple[int, tuple[str, ...]], ...], str]:
    """A branch's courses by semester (the college's own plan when we have it, else the typical one) and its source."""
    plans = _plans()
    key = college_of(college) if has_own_plan(exam, college) else "default"
    layout = plans["layouts"][exam][key]
    first = layout.get("first_year") or plans["first_year"].get(key) or plans["first_year"]["default"]
    by_sem = {**first, **layout["semesters"]}
    return tuple((n, tuple(by_sem.get(str(n), ()))) for n in SEMESTERS), layout["source"]


def _course_chapters(name: str, semester: int) -> list[Chapter]:
    out = []
    for c in courses()[name]["chapters"]:
        cid = f"{slug(name)}.{slug(c['name'])}"
        out.append(Chapter(id=cid, subject=name, unit=COURSE_UNIT, name=c["name"], cls=semester, hours=float(c["hours"]),
                           weight=float(c["weight"]), foundation=bool(c.get("foundation")),
                           topics=tuple(_topic(cid, t) for t in c["topics"])))
    return out


def _college(exam: str, college: str | None) -> Syllabus:
    semesters, source = semester_plan(exam, college)
    planned = {s: n for n, subjects in semesters for s in subjects}
    order = [*planned, *(name for name in courses() if name not in planned)]  # this branch's first, then every other course
    branch = BRANCHES[exam]
    return Syllabus(
        exam=exam, name=f"B.Tech {branch['name']}", subjects=tuple(order), units=tuple((s, COURSE_UNIT) for s in order),
        chapters=tuple(c for s in order for c in _course_chapters(s, planned.get(s, 0))), kind="college", library="college",
        college=college_of(college) if has_own_plan(exam, college) else "other", semesters=semesters, source=source,
        about=f"{source} Weightage is roughly how much of a course's end-semester paper a chapter is worth; hours are "
              "self-study estimates for learning and practising it alongside your lectures. Your college may teach a course "
              "in another semester or under another name: change your subjects to match.")


def get(exam: str, college: str | None = None) -> Syllabus:
    """An exam's whole syllabus. For a college branch: every course in the library, the branch's own first, with
    ``college``'s semester plan."""
    if exam not in EXAMS:
        raise KeyError(exam)
    return _get(exam, college_of(college) if is_college(exam) else None)


@cache
def _gate(exam: str) -> Syllabus:
    paper = PAPERS[exam]
    chapters: list[Chapter] = []
    for subject in paper["subjects"]:
        own = _course_chapters(subject["course"], 0)
        total = sum(c.weight for c in own)
        # a chapter's weight is its share of the paper: the subject's marks, split by the chapters' own weights
        chapters += [Chapter(c.id, c.subject, c.unit, c.name, c.cls, c.hours, round(subject["marks"] * c.weight / total, 2),
                             c.foundation, c.topics) for c in own]
    names = tuple(s["course"] for s in paper["subjects"])
    return Syllabus(exam=exam, name=f"GATE {paper['name']}", subjects=names, units=tuple((s, COURSE_UNIT) for s in names),
                    chapters=tuple(chapters), kind="gate", library="college",
                    about="Built on the GATE syllabus for this paper. General Aptitude carries 15 marks and Engineering "
                          "Mathematics about 13 (official); how the other marks split between subjects is an estimate "
                          "from recent papers and changes every year. Hours are self-study estimates for revising a "
                          "chapter you have met in college and practising it at GATE level.")


@cache
def _placement() -> Syllabus:
    """Placement preparation: the subjects the rounds test, weighted like a paper (so it is planned like one: kind
    "gate" means library courses with one date to be ready by)."""
    raw = _raw(PLACEMENT)
    chapters: list[Chapter] = []
    for subject in raw["subjects"]:
        own = _course_chapters(subject["course"], 0)
        total = sum(c.weight for c in own)
        chapters += [Chapter(c.id, c.subject, c.unit, c.name, c.cls, c.hours, round(subject["weight"] * c.weight / total, 2),
                             c.foundation, c.topics) for c in own]
    names = tuple(s["course"] for s in raw["subjects"])
    return Syllabus(exam=PLACEMENT, name=raw["name"], subjects=names, units=tuple((s, COURSE_UNIT) for s in names),
                    chapters=tuple(chapters), kind="gate", library="college", about=raw["about"])


@cache
def _school_raw(cls: int) -> dict:
    return json.loads((SCHOOL_DIR / f"class_{cls:02d}.json").read_text(encoding="utf-8"))


def _unique(key: str, seen: set[str], n: int) -> str:
    key = key if key not in seen else f"{key}-{n}"
    seen.add(key)
    return key


@cache
def _school(exam: str) -> Syllabus:
    """A school class: its subjects as NCERT's books for the class have them. A chapter's weight is its share of the
    marks where CBSE publishes them (Classes 9-12), else all chapters weigh the same."""
    cls = SCHOOL[exam]
    raw = _school_raw(cls)
    units: list = []
    chapters: list = []
    for subject in raw["subjects"]:
        name = subject["name"]
        rows = [(u, c) for u in subject["units"] for c in u["chapters"]]
        known = [c["marks"] for _, c in rows if c.get("marks")]
        mean = sum(known) / len(known) if known else 0
        seen: set[str] = set()
        for n, (unit, c) in enumerate(rows, 1):
            cid = f"c{cls}.{slug(name)}.{_unique(slug(c['name']) or f'ch{n}', seen, n)}"
            weight = round(min(3.0, max(0.75, 1.5 * c["marks"] / mean)), 2) if c.get("marks") and mean else 1.5
            topic_ids: set[str] = set()
            topics = tuple(Topic(f"{cid}.{_unique(slug(t) or f't{i}', topic_ids, i)}", t) for i, t in enumerate(c["topics"], 1))
            if (name, unit["name"]) not in units:
                units.append((name, unit["name"]))
            chapters.append(Chapter(id=cid, subject=name, unit=unit["name"], name=c["name"], cls=cls,
                                    hours=float(c.get("hours") or round(SCHOOL_HOURS[cls] * (weight / 1.5) ** 0.5, 1)),
                                    weight=weight, foundation=False, topics=topics))
    board = " Weightage is the share of the year's CBSE paper a chapter carries; chapters CBSE has left out this year are not here." if cls >= 9 else ""
    return Syllabus(exam=exam, name=f"Class {cls} (CBSE, NCERT books)", subjects=tuple(s["name"] for s in raw["subjects"]),
                    units=tuple(units), chapters=tuple(chapters), kind="school", library="cbse",
                    about=f"Every Class {cls} subject by its NCERT book, chapter by chapter as the book lists them (2026-27 reprints)."
                          f"{board} Hours are self-study estimates. Pick the subjects you take under My subjects.")


@cache
def _school_chapters() -> dict[tuple[str, str], tuple[int, Chapter]]:
    return {(c.subject, c.name): (n, c) for exam, n in SCHOOL.items() for c in _school(exam).chapters}


def school_class(subject: str, chapter: str) -> int | None:
    """The school class a chapter belongs to (chapter names are unique within a subject across the classes)."""
    hit = _school_chapters().get((subject, chapter))
    return hit[0] if hit else None


def school_topics(subject: str, chapter: str) -> tuple[str, ...]:
    """What a school chapter covers, as its NCERT book's sections name it."""
    hit = _school_chapters().get((subject, chapter))
    return tuple(t.name for t in hit[1].topics) if hit else ()


# the board years: only Classes 10 and 12 take timed tests (chapter tests and a mock board exam); the other classes
# learn, practise and revise without them
TEST_CLASSES = (10, 12)


def has_tests(exam: str | None) -> bool:
    """Whether a student of this exam takes timed tests on Focs (every exam does, school only in a board year)."""
    return not is_school(exam) or SCHOOL[exam] in TEST_CLASSES


def school_subjects(exam: str) -> tuple[str, ...]:
    """The subjects a school student studies until they pick their own: their class's usual ones."""
    syl = get(exam)
    usual = _school_raw(SCHOOL[exam]).get("default") or syl.subjects
    return tuple(s for s in syl.subjects if s in usual)


def _get(exam: str, college: str | None) -> Syllabus:
    if is_college(exam):
        return _college(exam, college)
    if is_gate(exam):
        return _gate(exam)
    if is_school(exam):
        return _school(exam)
    if is_placement(exam):
        return _placement()
    raw = _raw(exam)
    units: list = []
    chapters: list = []
    for subject in raw["subjects"]:
        if "from" in subject:  # NEET Physics/Chemistry: the JEE chapters, at NEET depth and weightage
            source = next(s for s in _raw(subject["from"])["subjects"] if s["name"] == subject["name"])
            u, c = _subject(source, hours_factor=subject.get("hours_factor", 1.0), weights=subject.get("weights"))
        else:
            u, c = _subject(subject)
        units += u
        chapters += c
    return Syllabus(exam=exam, name=raw["name"], about=raw["about"], library=exam, kind="gate" if exam in GOVT else "entrance",
                    subjects=tuple(s["name"] for s in raw["subjects"]), units=tuple(units), chapters=tuple(chapters))


def exam_of(exam_target: str | None) -> str | None:
    """The syllabus a student follows, from their exam target (others have no Prep Hub yet)."""
    exam = EXAM_OF_TARGET.get(exam_target or "", exam_target)
    return exam if exam in EXAMS else None


def semester_of(value: Any) -> int | None:
    """A semester number from what is stored for a student (3, "3", "Semester 3"), or None."""
    found = re.search(r"\d+", str(value)) if value is not None else None
    n = int(found.group()) if found else 0
    return n if n in SEMESTERS else None


def student_subjects(syl: Syllabus, semester: int | None, picked: list[str] | None) -> tuple[str, ...]:
    """The courses a college student is studying: the ones they picked, else their semester's in the plan. A
    semester with no taught courses (GGSIPU's 8th is the major project or internship) keeps the last semester's."""
    mine = tuple(dict.fromkeys(s for s in picked or [] if syl.has_subject(s)))
    return mine or next((s for n in range(semester or 1, 0, -1) if (s := syl.semester_subjects(n))), ())


@lru_cache(maxsize=512)
def _scoped(exam: str, college: str, subjects: tuple[str, ...]) -> Syllabus:
    return get(exam, college).only(subjects)


def of(user: Any, *, whole: bool = False) -> Syllabus | None:
    """The syllabus a student works on, or None when their exam has none. A college student's is their own
    subjects (``whole``: every course, for looking up a topic of any of them)."""
    exam = exam_of(getattr(user, "exam_target", None))
    if exam is None:
        return None
    if is_school(exam):  # the subjects they take; their class's usual ones until they say
        full = get(exam)
        if whole:
            return full
        mine = [s for s in getattr(user, "subjects", None) or [] if full.has_subject(s)] or list(school_subjects(exam))
        return full if len(mine) == len(full.subjects) else _scoped(exam, None, tuple(s for s in full.subjects if s in mine))
    if not is_college(exam):
        return get(exam)
    college = college_of(getattr(user, "college", None))
    full = get(exam, college)
    if whole:
        return full
    semester = semester_of(getattr(user, "semester", None))
    return _scoped(exam, college, student_subjects(full, semester, getattr(user, "subjects", None)))


# ---------------------------------------------------------------- wording
LABELS = {"jee": "JEE", "neet": "NEET", "ssc_cgl": "SSC CGL", "upsc": "UPSC", "gate": "GATE", "ca": "CA", "cbse": "CBSE board",
          "coding": "coding interview", "other": "exam"}


def label(exam_target: str | None) -> str:
    """How to name a student's exam to the AI ("a meticulous {label} teacher", "{label} students")."""
    exam = exam_of(exam_target)
    if is_college(exam):
        return f"B.Tech {BRANCHES[exam]['short']}"
    if is_gate(exam):
        return f"GATE {PAPERS[exam]['short']}"
    if is_school(exam):
        return f"CBSE Class {SCHOOL[exam]}"
    return LABELS.get(exam_target or "", (exam_target or "exam").upper())


def place(chapter: Chapter, syl: Syllabus | None = None) -> str:
    """Where a chapter sits, for a prompt: "Physics, Class 11" or "the B.Tech course Operating Systems"."""
    if chapter.unit == COURSE_UNIT or (syl is not None and syl.is_college):
        return f"the B.Tech course {chapter.subject}"
    if chapter.cls == 0:  # SSC: no classes
        return f"{chapter.subject} ({chapter.unit})"
    return f"{chapter.subject}, Class {chapter.cls}"


def weight_label(weight: float) -> str:
    return "high" if weight >= 2 else "medium" if weight >= 1.5 else "low"
