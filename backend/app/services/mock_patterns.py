"""Exam patterns for full mock tests (JEE Main, NEET and SSC CGL), and the syllabus they draw from.

Chapter weights are the approximate share of questions a chapter gets in recent JEE Main papers;
they decide how a paper's questions are spread, not how many exist in the bank.

College students have no single paper to mock: their tests are on one course (a "subject test" over all of its
chapters, or a chapter test on some), all MCQs, drawn from the same bank under the course's name.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

SUBJECTS = ("Physics", "Chemistry", "Mathematics")
SSC_SUBJECTS = ("General Intelligence and Reasoning", "General Awareness", "Quantitative Aptitude", "English Comprehension")
EXAM_SUBJECTS = {"jee": SUBJECTS, "neet": ("Physics", "Chemistry", "Biology"), "ssc_cgl": (*SSC_SUBJECTS, "Computer Knowledge")}
EXAM_LABEL = {"jee": "JEE Main", "neet": "NEET", "ssc_cgl": "SSC CGL"}


@dataclass(frozen=True)
class Section:
    key: str            # "A" | "B"
    qtype: str          # mcq | numerical
    count: int          # questions in the paper
    attempt: int        # how many are evaluated (Section B of the 30-question pattern: any 5 of 10)
    correct: float = 4
    wrong: float = -1
    label: str = ""


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    short: str
    description: str
    duration_min: int
    sections: tuple[Section, ...]
    subjects: tuple[str, ...] = SUBJECTS
    notes: tuple[str, ...] = field(default_factory=tuple)
    chapters: tuple[str, ...] = ()  # chapter tests draw only from these
    exam: str = "jee"               # whose questions it uses: jee | neet | ssc_cgl | college | cbse
    # a paper whose subjects don't all get the same number of questions (GATE): subject → section key → count
    counts: dict = field(default_factory=dict)
    # chapters only some of whose topics are tested (a last-day test): subject → chapter name → those topics' names
    # (by subject: NEET has a "Biomolecules" in Chemistry and in Biology)
    topics: dict = field(default_factory=dict)
    # the bank level its questions are written at, when not the exam's own (JEE Advanced papers: "jee_advanced")
    level: str = ""

    def sections_for(self, subject: str) -> tuple[Section, ...]:
        """The sections of one subject, with the number of questions that subject gets in each."""
        if not self.counts:
            return self.sections
        mine = self.counts.get(subject, {})
        return tuple(replace(s, count=mine[s.key], attempt=mine[s.key]) for s in self.sections if mine.get(s.key))

    @property
    def per_subject(self) -> int:
        return sum(s.count for s in self.sections)

    @property
    def total_questions(self) -> int:
        return sum(s.count for subject in self.subjects for s in self.sections_for(subject))

    @property
    def max_score(self) -> int:
        return int(round(sum(s.attempt * s.correct for subject in self.subjects for s in self.sections_for(subject))))

    def public(self) -> dict:
        return {
            "id": self.id, "name": self.name, "short": self.short, "description": self.description,
            "duration_min": self.duration_min, "subjects": list(self.subjects), "per_subject": self.per_subject,
            "total_questions": self.total_questions, "max_score": self.max_score, "notes": list(self.notes),
            "chapters": list(self.chapters), "exam": self.exam,
            "sections": [{"key": s.key, "qtype": s.qtype, "count": s.count, "attempt": s.attempt,
                          "correct": s.correct, "wrong": round(s.wrong, 2), "label": s.label} for s in self.sections],
            # subject → its number of questions, when subjects get different numbers (GATE, a last-day test)
            "subject_counts": {s: sum(x.count for x in self.sections_for(s)) for s in self.subjects} if self.counts else None,
        }


PATTERNS: dict[str, Pattern] = {
    p.id: p for p in (
        Pattern(
            id="jee_main_30", name="JEE Main · 30 + 30 + 30 (pre-2025)", short="90 questions",
            description="Physics, Chemistry and Mathematics, 30 questions each: 20 single-correct MCQs and "
                        "10 numerical-value questions, of which you answer any 5.",
            duration_min=180,
            sections=(
                Section("A", "mcq", 20, 20, 4, -1, "Section A · MCQ (single correct)"),
                Section("B", "numerical", 10, 5, 4, -1, "Section B · Numerical value (answer any 5)"),
            ),
            notes=("+4 for a correct answer, −1 for a wrong one, 0 if you leave it.",
                   "In Section B only 5 of the 10 questions per subject can be answered.",
                   "Numerical answers are integers — type them with the on-screen keypad or your keyboard."),
        ),
        Pattern(
            id="jee_main_25", name="JEE Main · 25 + 25 + 25", short="75 questions",
            description="The current NTA pattern: 25 questions per subject — 20 single-correct MCQs and "
                        "5 compulsory numerical-value questions.",
            duration_min=180,
            sections=(
                Section("A", "mcq", 20, 20, 4, -1, "Section A · MCQ (single correct)"),
                Section("B", "numerical", 5, 5, 4, -1, "Section B · Numerical value"),
            ),
            notes=("+4 for a correct answer, −1 for a wrong one, 0 if you leave it.",
                   "All Section B questions are compulsory.",
                   "Numerical answers are integers — type them with the on-screen keypad or your keyboard."),
        ),
        Pattern(
            id="jee_advanced", name="JEE Advanced style · 16 + 16 + 16", short="48 questions",
            description="Advanced-level questions for IIT aspirants: per subject, 8 single-correct MCQs (+3/−1) and "
                        "8 numerical-value questions (+4, no negative). A practice paper in the Advanced style, not a "
                        "copy of one year's pattern (which changes every year).",
            duration_min=180, level="jee_advanced",
            sections=(
                Section("A", "mcq", 8, 8, 3, -1, "Section A · MCQ (single correct, Advanced level)"),
                Section("B", "numerical", 8, 8, 4, 0, "Section B · Numerical value (no negative marking)"),
            ),
            notes=("+3 for a correct MCQ, −1 for a wrong one; +4 for a correct numerical, 0 for a wrong one.",
                   "Questions are at JEE Advanced level: expect several concepts in one question.",
                   "Numerical answers are integers — type them with the on-screen keypad or your keyboard."),
        ),
        Pattern(
            id="neet_180", name="NEET UG · 180 questions", short="180 questions", exam="neet",
            description="The current NTA pattern: Physics, Chemistry, Botany and Zoology, 45 single-correct "
                        "MCQs each, all compulsory, in 3 hours 20 minutes.",
            duration_min=200, subjects=("Physics", "Chemistry", "Botany", "Zoology"),
            sections=(Section("A", "mcq", 45, 45, 4, -1, "MCQ (single correct)"),),
            notes=("+4 for a correct answer, −1 for a wrong one, 0 if you leave it.",
                   "All 180 questions are compulsory: there is no choice between questions.",
                   "Botany and Zoology together make up Biology, half of the paper."),
        ),
        Pattern(
            id="ssc_cgl_t1", name="SSC CGL Tier-I · 100 questions", short="100 questions · 60 min", exam="ssc_cgl",
            description="The current SSC pattern: Reasoning, General Awareness, Quantitative Aptitude and English, 25 "
                        "single-correct MCQs each, in one hour.",
            duration_min=60, subjects=SSC_SUBJECTS,
            sections=(Section("A", "mcq", 25, 25, 2, -0.5, "MCQ (single correct)"),),
            notes=("+2 for a correct answer, −0.5 for a wrong one, 0 if you leave it.",
                   "100 questions in 60 minutes: about 36 seconds a question, so skip what's slow and come back.",
                   "Real past-paper (PYQ) questions are used where the bank has them; each shows its year and shift."),
        ),
        Pattern(
            id="ssc_cgl_t2", name="SSC CGL Tier-II · Paper-I", short="150 questions · 2 h 15 min", exam="ssc_cgl",
            description="Paper-I, Session I: Mathematical Abilities 30 and Reasoning 30 (Section I), English 45 and "
                        "General Awareness 25 (Section II), and the Computer Knowledge module, 20 (Section III).",
            duration_min=135, subjects=("Quantitative Aptitude", "General Intelligence and Reasoning", "English Comprehension",
                                        "General Awareness", "Computer Knowledge"),
            counts={"Quantitative Aptitude": {"A": 30}, "General Intelligence and Reasoning": {"A": 30},
                    "English Comprehension": {"A": 45}, "General Awareness": {"A": 25}, "Computer Knowledge": {"A": 20}},
            sections=(Section("A", "mcq", 0, 0, 3, -1, "MCQ (single correct)"),),
            notes=("+3 for a correct answer, −1 for a wrong one, 0 if you leave it.",
                   "The real exam times its three sections separately (1 h, 1 h and 15 min); here one clock runs for all.",
                   "Computer Knowledge is qualifying in the real exam: its marks don't count towards the merit."),
        ),
    )
}
# the current NTA paper (5 compulsory numericals); the 90-question one is the pre-2025 pattern, kept for practice
DEFAULT_PATTERN = "jee_main_25"
DEFAULT_PATTERNS = {"jee": "jee_main_25", "neet": "neet_180", "ssc_cgl": "ssc_cgl_t1"}

# chapter -> weight (relative share of questions)
SYLLABUS: dict[str, dict[str, float]] = {
    "Physics": {
        "Units, Measurements & Errors": 1, "Kinematics": 2, "Laws of Motion": 1.5, "Work, Energy & Power": 1.5,
        "Rotational Motion": 2, "Gravitation": 1.5, "Properties of Solids & Liquids": 1.5, "Thermodynamics": 1.5,
        "Kinetic Theory of Gases": 1, "Oscillations & Waves": 2, "Electrostatics": 2.5, "Current Electricity": 2,
        "Magnetic Effects of Current & Magnetism": 2.5, "Electromagnetic Induction & AC": 1.5,
        "Electromagnetic Waves": 1, "Ray & Wave Optics": 2.5, "Dual Nature of Matter & Radiation": 1.5,
        "Atoms & Nuclei": 1.5, "Semiconductor Electronics": 1.5,
    },
    "Chemistry": {
        "Some Basic Concepts of Chemistry": 1, "Atomic Structure": 1.5, "Chemical Bonding & Molecular Structure": 2,
        "Chemical Thermodynamics": 1.5, "Solutions": 1, "Equilibrium": 1.5, "Redox Reactions & Electrochemistry": 1.5,
        "Chemical Kinetics": 1.5, "Classification of Elements & Periodicity": 1, "p-Block Elements": 1.5,
        "d- and f-Block Elements": 1.5, "Coordination Compounds": 2, "Purification & Characterisation of Organic Compounds": 1,
        "General Organic Chemistry": 2, "Hydrocarbons": 1.5, "Haloalkanes & Haloarenes": 1,
        "Alcohols, Phenols & Ethers": 1, "Aldehydes, Ketones & Carboxylic Acids": 1.5,
        "Amines & Nitrogen Compounds": 1, "Biomolecules": 1,
    },
    "Mathematics": {
        "Sets, Relations & Functions": 1.5, "Complex Numbers": 1.5, "Quadratic Equations": 1,
        "Matrices & Determinants": 2, "Permutations & Combinations": 1, "Binomial Theorem": 1,
        "Sequences & Series": 1.5, "Limits, Continuity & Differentiability": 2, "Application of Derivatives": 1,
        "Integral Calculus": 2.5, "Differential Equations": 1, "Straight Lines": 1, "Circles": 1,
        "Conic Sections": 2, "Three Dimensional Geometry": 2, "Vector Algebra": 1.5,
        "Statistics": 1, "Probability": 1.5, "Trigonometry": 1,
    },
}


def _biology() -> dict[str, float]:
    from app.services import syllabus  # the NEET syllabus file holds Biology's chapters and weightage
    return {c.name: c.weight for c in syllabus.get("neet").subject_chapters("Biology")}


SYLLABUS["Biology"] = _biology()


def _ssc() -> dict[str, dict[str, float]]:
    from app.services import syllabus
    syl = syllabus.get("ssc_cgl")
    return {s: {c.name: c.weight for c in syl.subject_chapters(s)} for s in syl.subjects}


SYLLABUS.update(_ssc())

# How NEET papers (and coaching) split Biology: plant biology is Botany, animal and human biology is Zoology.
ZOOLOGY = frozenset({
    "Animal Kingdom", "Structural Organisation in Animals", "Biomolecules", "Breathing and Exchange of Gases",
    "Body Fluids and Circulation", "Excretory Products and their Elimination", "Locomotion and Movement",
    "Neural Control and Coordination", "Chemical Coordination and Integration", "Human Reproduction",
    "Reproductive Health", "Evolution", "Human Health and Disease", "Biotechnology: Principles and Processes",
    "Biotechnology and its Applications",
})
BOTANY = frozenset(SYLLABUS["Biology"]) - ZOOLOGY


def bank_source(subject: str, chapters: tuple[str, ...] | list[str] = ()) -> tuple[str, tuple[str, ...]]:
    """Where a paper section's questions come from: Botany and Zoology are halves of the bank's Biology."""
    if subject in ("Botany", "Zoology"):
        half = BOTANY if subject == "Botany" else ZOOLOGY
        return "Biology", tuple(c for c in SYLLABUS["Biology"] if c in half and (not chapters or c in chapters))
    return subject, tuple(chapters)


CHAPTER_TEST_SIZES = (10, 15, 20, 25)
COURSE_TEST_SIZES = (10, 15, 20, 25, 30)  # a test on a whole course can run to thirty questions
MINUTES_PER_QUESTION = 2  # a little under JEE Main's 2.4 minutes, to build speed
BOARD_MOCK_QUESTIONS = 50  # a mock board exam (Class 10 and 12): the whole subject
BOARD_MOCK_MINUTES = 90
SSC_MINUTES = 0.6         # SSC CGL Tier-I: 100 questions in an hour


def chapters_of(subject: str | None) -> dict[str, float]:
    """A subject's chapters and their weights: a JEE/NEET subject, or a course of the college library. {} if neither."""
    if subject in SYLLABUS:
        return SYLLABUS[subject]
    from app.services import syllabus

    course = syllabus.courses().get(subject or "")
    return {c["name"]: float(c["weight"]) for c in course["chapters"]} if course else {}


def is_course(subject: str | None) -> bool:
    return subject not in SYLLABUS and bool(chapters_of(subject))


def chapter_pattern(subject: str, chapters: list[str], count: int, exam: str = "jee", board: bool = False) -> Pattern:
    """A short test on chosen chapters of one subject, all compulsory: JEE ~70% MCQs and the rest numerical,
    NEET all MCQs (like the real paper). ``board``: a Class 10 or 12 mock board exam on the whole subject."""
    if board:
        return Pattern(
            id="chapter", name=f"Mock board exam · {subject}", short=f"{count} questions · whole syllabus",
            description=f"A timed board-style paper on all of {subject}: {count} questions across every chapter of "
                        "this year's CBSE syllabus.", exam="cbse",
            duration_min=BOARD_MOCK_MINUTES, subjects=(subject,), chapters=tuple(chapters),
            sections=(Section("A", "mcq", count, count, 1, 0, "MCQ (single correct)"),),
            notes=("1 mark for a correct answer. No negative marking, so answer every question.",
                   "Every chapter of this year's CBSE syllabus is in it, like the real board paper.",
                   "The real board paper also has short and long written answers: practise those under Practice, "
                   "where Focs marks them like an examiner."),
        )
    label = chapters[0] if len(chapters) == 1 else f"{len(chapters)} chapters"
    if exam == "college" or is_course(subject):
        whole = len(chapters) == len(chapters_of(subject))
        return Pattern(
            id="chapter", name=f"{'Subject' if whole else 'Chapter'} test · {subject}",
            short=f"{count} questions · {'all chapters' if whole else label}",
            description=f"{count} questions on {subject if whole else ', '.join(chapters)}.", exam="college",
            duration_min=max(10, round(count * 1.5)), subjects=(subject,), chapters=tuple(chapters),
            sections=(Section("A", "mcq", count, count, 1, 0, "MCQ (single correct)"),),
            notes=("1 mark for a correct answer. No negative marking, so answer every question.",
                   "About a minute and a half a question.",
                   "Questions are written at university-exam level and cross-checked by a second AI model; "
                   "they are not from your college's past papers."),
        )
    if exam == "cbse":
        return Pattern(
            id="chapter", name=f"Chapter test · {subject}", short=f"{count} questions · {label}",
            description=f"{count} board-level questions on {', '.join(chapters)}.", exam="cbse",
            duration_min=max(10, round(count * 1.5)), subjects=(subject,), chapters=tuple(chapters),
            sections=(Section("A", "mcq", count, count, 1, 0, "MCQ (single correct)"),),
            notes=("1 mark for a correct answer. No negative marking, so answer every question.",
                   "The kind of objective and competency questions a board paper opens with, at NCERT level.",
                   "Written answers are practised under Practice, where Focs marks them like an examiner."),
        )
    if exam == "ssc_cgl" or subject in EXAM_SUBJECTS["ssc_cgl"]:
        return Pattern(
            id="chapter", name=f"Chapter test · {subject}", short=f"{count} questions · {label}",
            description=f"{count} SSC CGL questions on {', '.join(chapters)}.", exam="ssc_cgl",
            duration_min=max(5, round(count * SSC_MINUTES)), subjects=(subject,), chapters=tuple(chapters),
            sections=(Section("A", "mcq", count, count, 2, -0.5, "MCQ (single correct)"),),
            notes=("+2 for a correct answer, −0.5 for a wrong one, 0 if you leave it (Tier-I marking).",
                   "About 36 seconds a question, like the real Tier-I paper.",
                   "Chapter tests don't count towards your weekly full-mock limit."),
        )
    if exam == "neet" or subject == "Biology":
        return Pattern(
            id="chapter", name=f"Chapter test · {subject}", short=f"{count} questions · {label}",
            description=f"{count} NEET-style questions on {', '.join(chapters)}.", exam="neet",
            duration_min=max(5, round(count * 1.1)), subjects=(subject,), chapters=tuple(chapters),
            sections=(Section("A", "mcq", count, count, 4, -1, "MCQ (single correct)"),),
            notes=("+4 for a correct answer, −1 for a wrong one, 0 if you leave it.",
                   "About a minute a question, like the real NEET paper.",
                   "Chapter tests don't count towards your weekly full-mock limit."),
        )
    mcq = max(1, round(count * 0.7))
    return Pattern(
        id="chapter", name=f"Chapter test · {subject}", short=f"{count} questions · {label}",
        description=f"{count} questions on {', '.join(chapters)}.",
        duration_min=count * MINUTES_PER_QUESTION, subjects=(subject,), chapters=tuple(chapters),
        sections=(
            Section("A", "mcq", mcq, mcq, 4, -1, "Section A · MCQ (single correct)"),
            Section("B", "numerical", count - mcq, count - mcq, 4, -1, "Section B · Numerical value"),
        ),
        notes=("+4 for a correct answer, −1 for a wrong one, 0 if you leave it.",
               "Numerical answers are integers — type them with the on-screen keypad or your keyboard.",
               "Chapter tests don't count towards your weekly full-mock limit."),
    )


def revision_pattern(parts: list[dict], count: int, exam: str = "jee") -> Pattern:
    """The test that ends a day of last-day revision: on exactly what was revised, in every subject of the day's list.
    ``parts``: per subject, its chapters, the topics of the chapters only some of whose topics were on the list, and
    its number of questions. Marked like the student's exam: JEE's numericals and negative marks, NEET's MCQs, one
    mark and no negative marking for a semester or board test."""
    parts = [p for p in parts if p.get("count")]
    chapters = tuple(c for p in parts for c in p["chapters"])
    topics = {p["subject"]: {c: tuple(names) for c, names in p["topics"].items()} for p in parts if p.get("topics")}
    if exam == "jee":  # about 70% MCQs and the rest numerical, like the chapter tests
        counts = {p["subject"]: {"A": (a := max(1, round(p["count"] * 0.7))), "B": p["count"] - a} for p in parts}
        sections: tuple[Section, ...] = (Section("A", "mcq", 0, 0, 4, -1, "Section A · MCQ (single correct)"),
                                         Section("B", "numerical", 0, 0, 4, -1, "Section B · Numerical value"))
        minutes = count * MINUTES_PER_QUESTION
        marking = "+4 for a correct answer, −1 for a wrong one, 0 if you leave it."
    else:
        counts = {p["subject"]: {"A": p["count"]} for p in parts}
        one = exam in ("college", "cbse")
        ssc = exam == "ssc_cgl"
        sections = (Section("A", "mcq", 0, 0, 1 if one else 2 if ssc else 4, 0 if one else -0.5 if ssc else -1,
                            "MCQ (single correct)"),)
        minutes = max(10, round(count * (1.1 if exam == "neet" else SSC_MINUTES if ssc else 1.5)))
        marking = ("1 mark for a correct answer. No negative marking, so answer every question." if one
                   else "+2 for a correct answer, −0.5 for a wrong one, 0 if you leave it." if ssc
                   else "+4 for a correct answer, −1 for a wrong one, 0 if you leave it.")
    n = len(chapters)
    return Pattern(
        id="chapter", name="Last-day test", short=f"{count} questions · {n} chapter{'' if n == 1 else 's'}",
        description=f"{count} questions on the {n} chapter{'' if n == 1 else 's'} you revised today, and only the topics "
                    "you revised in them.",
        duration_min=minutes, sections=sections, subjects=tuple(p["subject"] for p in parts), chapters=chapters,
        exam=exam, counts=counts, topics=topics,
        notes=(marking,
               "Only the chapters on today's revision list, and in a chapter you revised in part, only those topics.",
               "Tests like this don't count towards your weekly full-mock limit."),
    )


def test_pattern(config: dict) -> Pattern:
    """A short test's pattern from what was stored for it: a last-day test, or a chapter or subject test."""
    if config.get("kind") == "revision":
        return revision_pattern(config["parts"], config["count"], config.get("exam", "jee"))
    return chapter_pattern(**config)


def chapter_targets(subject: str, n: int, chapters: list[str] | tuple[str, ...] | None = None) -> dict[str, int]:
    """Spread n questions over a subject's chapters (or the chosen ones) by weight (largest-remainder rounding)."""
    subject, chapters = bank_source(subject, chapters or ())
    weights = {c: w for c, w in chapters_of(subject).items() if not chapters or c in chapters}
    if not weights:  # a school subject's chapters (not JEE's or the college library's): all weigh the same
        weights = {c: 1.0 for c in chapters}
    total = sum(weights.values())
    raw = {c: n * w / total for c, w in weights.items()}
    out = {c: int(v) for c, v in raw.items()}
    for c in sorted(raw, key=lambda c: raw[c] - out[c], reverse=True)[: n - sum(out.values())]:
        out[c] += 1
    return out


# ---------------------------------------------------------------- GATE: one full paper per branch
GATE_QUESTIONS = {"1": 30, "2": 35}  # 65 questions: 30 of one mark and 35 of two, 100 marks in all
GATE_APTITUDE = {"1": 5, "2": 5}     # General Aptitude: 15 of the 100 marks


def _share(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Split a whole number by weights (largest remainders get the leftovers)."""
    whole = sum(weights.values()) or 1
    raw = {k: total * w / whole for k, w in weights.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[: total - sum(out.values())]:
        out[k] += 1
    return out


def gate_pattern(exam: str) -> Pattern:
    """A full GATE paper: 65 questions for 100 marks in 3 hours, General Aptitude first, then the paper's subjects
    in proportion to the marks they usually carry. All MCQs here (the real paper mixes in MSQ and numerical answers)."""
    from app.services import syllabus

    paper = syllabus.PAPERS[exam]
    marks = {s["course"]: s["marks"] for s in paper["subjects"] if s["course"] != "General Aptitude"}
    counts = {"General Aptitude": dict(GATE_APTITUDE)}
    for key in ("1", "2"):
        for subject, n in _share(GATE_QUESTIONS[key] - GATE_APTITUDE[key], marks).items():
            counts.setdefault(subject, {})[key] = n
    return Pattern(
        id=f"{exam}_full", name=f"GATE {paper['short']} · full paper", short="65 questions", exam="college",
        description=f"General Aptitude and {paper['name']}: 65 questions for 100 marks, split between subjects the way "
                    "recent papers have been.",
        duration_min=180, subjects=tuple(s["course"] for s in paper["subjects"]), counts=counts,
        sections=(Section("1", "mcq", 0, 0, 1, -1 / 3, "1-mark questions"), Section("2", "mcq", 0, 0, 2, -2 / 3, "2-mark questions")),
        notes=("1-mark questions: +1 for a correct answer, −⅓ for a wrong one. 2-mark questions: +2 and −⅔.",
               "Every question here is single-correct. The real paper also has multiple-select and numerical-answer "
               "questions, which carry no negative marks.",
               "An on-screen calculator is all GATE allows: keep yours away."),
    )


def _gate_patterns() -> dict[str, Pattern]:
    from app.services import syllabus

    return {p.id: p for p in map(gate_pattern, syllabus.PAPERS)}


PATTERNS.update(_gate_patterns())
