"""Prep Hub and the mentor plan: the syllabus with progress, the student's goal, and the plan built from both.

Days are the student's local days (tz_offset from the browser, minutes east of UTC; IST is 330).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api._common import library_capsule, library_notes
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.flashcard import Flashcard
from app.models.mock import MockTest
from app.models.note import Note
from app.models.prep import ChapterRevision, PlanCheck, PlanTask, StudyGoal, TopicProgress
from app.models.quiz_attempt import QuizAttempt
from app.models.session import StudySession
from app.models.study_day import StudyDay
from app.models.user import User
from app.models.weak import WeakTopic
from app.services import formulas, lastday, likely, mock, planner, question_bank, syllabus, topic_notes, weak
from app.services.mock_patterns import revision_pattern
from app.services.syllabus import Syllabus

router = APIRouter(prefix="/prep", tags=["prep"])

Track = Literal["jee_main", "jee_advanced", "neet", "college", "gate", "cbse", "placement", "ssc_cgl"]
ClassLevel = Literal["11", "12", "dropper", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]  # college: the semester; school: the class
SchoolClass = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
Level = Literal["none", "partial", "done"]
CLASS_LABEL = {"11": "Class 11", "12": "Class 12", "dropper": "Dropper"}
# done_at for topics a student covered before starting on Focs (onboarding): long finished, never "studied today"
COVERED_EARLIER = datetime(2000, 1, 1)  # noqa: DTZ001 (stored datetimes are naive UTC, like utcnow())


def _today(tz_offset: int) -> date:
    return (utcnow() + timedelta(minutes=tz_offset)).date()


def _local(dt: datetime | None, tz_offset: int) -> date | None:
    return (dt + timedelta(minutes=tz_offset)).date() if dt else None


def _goal_row(db: Session, user: User) -> StudyGoal | None:
    return db.scalar(select(StudyGoal).where(StudyGoal.user_id == user.id))


def _goal(db: Session, user: User) -> StudyGoal | None:
    """The student's goal, when it is for the syllabus they follow now. One set for another exam (they changed
    their exam in Settings since) is kept but not used, so going back brings the plan back."""
    g = _goal_row(db, user)
    if g is None:
        return None
    current = syllabus.exam_of(user.exam_target)
    if current is None:  # UPSC, CA, other: no syllabus here, and never another exam's plan (it comes back if they switch back)
        return None
    return g if g.exam == _goal_exam(current) else None


def _goal_exam(exam: str) -> str:
    """What a goal is stored under: the exam, and for every B.Tech branch "college" (the branch is the student's,
    so changing branch keeps the exam date, the grade aimed at and the hours); likewise "gate" and "cbse"."""
    return syllabus.group(exam) or exam


COLLEGE_GOAL = "college"


NO_SYLLABUS = ("The Prep Hub covers JEE, NEET, SSC CGL, GATE, B.Tech, placements and school (Class 1-12). Set one as what "
               "you're preparing for in Settings.")


def _syllabus(db: Session, user: User, requested: str | None = None, *, whole: bool = False) -> Syllabus:
    """The syllabus the student works on. A college student's is their own subjects; ``whole`` is every course,
    for finding a topic or chapter of any of them."""
    if requested in syllabus.ENTRANCE:
        return syllabus.get(requested)  # type: ignore[arg-type]
    goal = _goal(db, user)
    if goal is not None and goal.exam in syllabus.ENTRANCE:
        return syllabus.get(goal.exam)
    syl = syllabus.of(user, whole=whole)
    if syl is None:
        raise HTTPException(status_code=404, detail=NO_SYLLABUS)
    return syl


def _progress(db: Session, user: User, syl: Syllabus, tz_offset: int, today: date) -> planner.Progress:
    prefix = tuple({c.id.rsplit(".", 1)[0] + "." for c in syl.chapters})  # a subject's IDs ("physics.", or a class's "c12.physics.")
    done = {tid: date.min if not at or at <= COVERED_EARLIER else _local(at, tz_offset) for tid, at in db.execute(
        select(TopicProgress.topic_id, TopicProgress.done_at).where(TopicProgress.user_id == user.id)).all()
        if tid.startswith(prefix)}
    revisions: dict[str, list[date]] = {}
    for cid, at in db.execute(select(ChapterRevision.chapter_id, ChapterRevision.revised_at)
                              .where(ChapterRevision.user_id == user.id)).all():
        revisions.setdefault(cid, []).append(_local(at, tz_offset) or today)
    checks = set(db.scalars(select(PlanCheck.task).where(PlanCheck.user_id == user.id, PlanCheck.day == today)))
    focus = db.scalar(select(func.coalesce(func.sum(StudyDay.minutes), 0))
                      .where(StudyDay.user_id == user.id, StudyDay.day > today - timedelta(days=7)))
    own = db.scalars(select(PlanTask).where(PlanTask.user_id == user.id, PlanTask.day == today).order_by(PlanTask.id)).all()
    day_start = datetime.combine(today, datetime.min.time()) - timedelta(minutes=tz_offset)  # local midnight, in UTC
    return planner.Progress(done_topics=done, revisions=revisions, checks=checks, focus_minutes_week=int(focus or 0),
                            custom=[{"id": t.id, "title": t.title, "minutes": t.minutes, "done": bool(t.done)} for t in own],
                            weak=weak.for_plan(db, user.id, syl, day_start))


def _plan_goal(g: StudyGoal, syl: Syllabus) -> planner.Goal:
    day_hours, pinned, skipped = planner.clean_edits(syl, g.edits)
    return planner.Goal(exam=syl.exam, track=g.track, class_level=g.class_level, exam_date=g.exam_date, target=g.target,
                        weekday_hours=g.weekday_hours, weekend_hours=g.weekend_hours, day_hours=day_hours, pinned=pinned,
                        skipped=skipped)


def _goal_out(g: StudyGoal, user: User) -> dict[str, Any]:
    own = g.exam in planner.OWN_TRACKS
    return {"exam": syllabus.exam_of(user.exam_target) if own else g.exam, "group": g.exam,
            "kind": {"college": "college", "gate": "gate", "cbse": "school", "placement": "gate", "ssc_cgl": "gate"}.get(g.exam, "entrance"),
            "track": g.track, "class_level": g.class_level, "exam_date": g.exam_date.isoformat(),
            "target": g.target, "dream": g.dream, "weekday_hours": g.weekday_hours, "weekend_hours": g.weekend_hours,
            "coaching": g.coaching, "standing": g.standing or {}}


def _built(db: Session, user: User, g: StudyGoal, tz_offset: int, *, rebase: bool = False) -> dict[str, Any]:
    """The student's plan as the pages read it. ``rebase``: the plan itself just changed (hours, exam date, a chapter
    left out), so "where you should be by now" starts again from today instead of calling the student behind."""
    today = _today(tz_offset)
    syl = _syllabus(db, user)
    progress = _progress(db, user, syl, tz_offset, today)
    if rebase or (g.created_at and (utcnow() - g.created_at).days < 7):
        progress.focus_minutes_week = None  # a week of the plan before judging how it's going
    plan = planner.build(_plan_goal(g, syl), syl, progress, today, baseline=None if rebase else g.baseline)
    if rebase:
        g.baseline, plan["expected_now"] = plan["baseline"], plan["completion"]  # on track by definition, as of today
    db.commit()  # the edit that led here, if any
    plan["goal"] = _goal_out(g, user)
    plan.pop("baseline", None)
    return plan


# ---------------------------------------------------------------- goal
@router.get("/options")
def options(tz_offset: int = Query(330, ge=-840, le=840)) -> dict[str, Any]:
    """Everything onboarding needs: exams, goals, the subjects to ask about and suggested exam dates."""
    today = _today(tz_offset)
    dates = {track: {cls: planner.default_exam_date(track, cls, today).isoformat() for cls in CLASS_LABEL}
             for track in planner.TRACKS}
    choices = {track: sorted({d.isoformat() for y in range(today.year, today.year + 3)
                              for d in planner.exam_dates(track, y) if today + timedelta(days=14) < d})[:4]
               for track in planner.TRACKS}
    college = [{"date": d.isoformat(), "label": name} for d, name in planner.college_exam_dates(today)]
    gate = planner.gate_exam_date(today)
    rounds = {"gate": [{"date": gate.isoformat(), "label": f"GATE {gate.year}"}],
              "placement": [{"date": d.isoformat(), "label": name} for d, name in planner.placement_dates(today)],
              "ssc_cgl": [{"date": d.isoformat(), "label": name} for d, name in planner.ssc_dates(today)],
              **{exam: [{"date": d.isoformat(), "label": name} for d, name in planner.board_exam_dates(today, cls)]
                 for exam, cls in syllabus.SCHOOL.items()}}
    return {"tracks": [{"id": k, **v} for k, v in planner.TRACKS.items()], "targets": planner.TARGETS,
            "subjects": {e: list(syllabus.get(e).subjects) for e in syllabus.ENTRANCE},
            "default_dates": dates, "date_choices": choices,
            "college": {"dates": college, "default_date": planner.default_college_exam_date(today).isoformat()},
            # GATE, placements and the boards: the coming rounds (approximate), by exam ("gate", "placement", "cbse_11", "cbse_12")
            "rounds": rounds}


class SubjectsIn(BaseModel):
    subjects: list[str] = Field(min_length=1, max_length=16)


@router.put("/subjects")
def set_subjects(body: SubjectsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A school student's subjects (PCM, PCB, commerce, humanities…): their Prep Hub, plan and tests follow them."""
    exam = syllabus.exam_of(user.exam_target)
    if not syllabus.is_school(exam):
        raise HTTPException(status_code=404, detail="This is for school students.")
    full = syllabus.get(exam)
    mine = [s for s in full.subjects if s in body.subjects]
    if not mine:
        raise HTTPException(status_code=422, detail="Pick at least one subject.")
    user.subjects = None if len(mine) == len(full.subjects) else mine
    g = _goal(db, user)
    if g is not None:
        g.baseline = []  # other subjects: "on track" is measured from now
    db.commit()
    return {"subjects": mine, "all": list(full.subjects)}


# ---------------------------------------------------------------- college: branch, college, semester and subjects
MAX_SUBJECTS = 10  # in one semester


def _college_out(user: User, college: str | None = None, semester: int | None = None) -> dict[str, Any]:
    """What a college student's set-up shows: the semester plan of their branch at a college, the courses of every
    semester, and the whole course library to pick from. ``college`` / ``semester``: look at another one before saving."""
    exam = syllabus.exam_of(user.exam_target)
    if not syllabus.is_college(exam):
        raise HTTPException(status_code=404, detail="This is for B.Tech students. Choose your branch in Settings first.")
    chosen = syllabus.college_of(college or user.college)
    sem = semester or syllabus.semester_of(user.semester) or syllabus.semester_of(user.class_level)
    full = syllabus.get(exam, chosen)
    same = chosen == syllabus.college_of(user.college) and sem == syllabus.semester_of(user.semester)
    picked = [s for s in (user.subjects or []) if full.has_subject(s)] if same else []
    library = syllabus.courses()
    return {
        "branch": syllabus.BRANCHES[exam], "branches": list(syllabus.BRANCHES.values()),
        "college": chosen, "semester": sem, "saved": user.semester is not None,
        "colleges": [{**c, "has_plan": syllabus.has_own_plan(exam, c["id"])} for c in syllabus.COLLEGES.values()],
        "own_plan": syllabus.has_own_plan(exam, chosen), "source": full.source,
        "semesters": [{"n": n, "subjects": list(subjects)} for n, subjects in full.semesters],
        "subjects": picked or list(syllabus.student_subjects(full, sem, None)), "picked": bool(picked),
        "catalogue": [{"name": name, "about": c.get("about", ""), "area": c["area"], "semester": full.semester_of(name),
                       "chapters": len(c["chapters"]), "topics": sum(len(ch["topics"]) for ch in c["chapters"]),
                       "hours": round(sum(ch["hours"] for ch in c["chapters"]))} for name, c in library.items()],
        "max_subjects": MAX_SUBJECTS,
    }


@router.get("/college")
def college_setup(college: str | None = Query(None, max_length=20), semester: int | None = Query(None, ge=1, le=8),
                  user: User = Depends(get_current_user)) -> dict[str, Any]:
    return _college_out(user, college, semester)


class CollegeIn(BaseModel):
    college: Literal["iitd", "iiitd", "dtu", "nsut", "ggsipu", "aktu", "other"] = "other"
    semester: int = Field(ge=1, le=8)
    subjects: list[str] | None = Field(None, max_length=MAX_SUBJECTS)  # None: the plan's courses for the semester


@router.put("/college")
def set_college(body: CollegeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Save where a college student studies, their semester and the courses they are taking in it."""
    exam = syllabus.exam_of(user.exam_target)
    if not syllabus.is_college(exam):
        raise HTTPException(status_code=404, detail="This is for B.Tech students. Choose your branch in Settings first.")
    full = syllabus.get(exam, body.college)
    subjects = None
    if body.subjects is not None:
        subjects = list(dict.fromkeys(s for s in body.subjects if full.has_subject(s)))
        if not subjects:
            raise HTTPException(status_code=422, detail="Pick at least one subject.")
        if tuple(subjects) == syllabus.student_subjects(full, body.semester, None):
            subjects = None  # exactly the plan: keep following it
    user.college, user.semester, user.subjects = body.college, body.semester, subjects
    user.class_level = f"Semester {body.semester}"
    g = _goal(db, user)
    if g is not None and g.class_level != str(body.semester):
        g.class_level, g.baseline = str(body.semester), []  # a new semester: "on track" starts again
    db.commit()
    return _college_out(user)


class GoalIn(BaseModel):
    track: Track
    class_level: ClassLevel
    exam_date: date
    target: str = Field(max_length=20)
    dream: str | None = Field(None, max_length=120)
    weekday_hours: float = Field(ge=0.5, le=16)
    weekend_hours: float = Field(ge=0, le=16)
    coaching: Literal["self", "online", "offline"] = "self"
    standing: dict[str, dict[SchoolClass | Literal["all"], Level]] = Field(default_factory=dict)  # by class; college: {"subject": {"all": …}}
    apply_standing: bool = False  # mark the topics the student says they've covered (first set-up)

    @field_validator("dream")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


@router.get("/goal")
def get_goal(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any] | None:
    g = _goal(db, user)
    return _goal_out(g, user) if g else None


@router.put("/goal")
def set_goal(body: GoalIn, tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> dict[str, Any]:
    today = _today(tz_offset)
    college = body.track == planner.COLLEGE_TRACK
    own = body.track in planner.OWN_TRACKS  # the exam is the one in the student's profile (a branch, a paper, a class)
    mine = syllabus.exam_of(user.exam_target)
    school = own and syllabus.is_school(mine)
    if college and body.class_level not in {str(n) for n in syllabus.SEMESTERS}:
        raise HTTPException(status_code=422, detail="Choose your semester.")
    if not college and not school and body.class_level not in CLASS_LABEL and body.track != "ssc_cgl":  # an entrance exam: Class 11, 12 or a dropper
        raise HTTPException(status_code=422, detail="Choose your class.")
    if own:
        exam = mine
        if syllabus.group(exam) != body.track:
            raise HTTPException(status_code=422, detail="Choose what you're preparing for in Settings first.")
        if college and syllabus.semester_of(user.semester) != int(body.class_level):
            user.semester, user.subjects = int(body.class_level), None  # the plan's courses for the semester just chosen
        if syllabus.is_school(exam) and body.class_level != str(syllabus.SCHOOL[exam]):
            raise HTTPException(status_code=422, detail="Choose your class.")
    else:
        exam = planner.TRACKS[body.track]["exam"]
    if body.target not in {t["id"] for t in planner.TARGETS[planner.family(exam)]}:
        raise HTTPException(status_code=422, detail="Pick one of the goals offered for this exam.")
    if not today < body.exam_date <= today + timedelta(days=3 * 366):
        raise HTTPException(status_code=422, detail="The exam date should be within the next three years.")
    user.exam_target = exam if not own else user.exam_target
    if body.track not in ("gate", "placement", "ssc_cgl"):  # (a GATE or placement aspirant's "class" is whatever they wrote in their profile)
        user.class_level = f"Semester {body.class_level}" if college else CLASS_LABEL.get(body.class_level, f"Class {body.class_level}")
    syl = syllabus.of(user) if own else syllabus.get(exam)
    standing = {s: lv for s, lv in body.standing.items() if s in syl.subjects}
    g = _goal_row(db, user)
    stored = _goal_exam(exam)
    first = g is None or g.exam != stored  # nothing set yet, or what is there was for another syllabus
    if g is None:
        g = StudyGoal(user_id=user.id)
        db.add(g)
    if g.exam and g.exam != stored:
        g.edits, g.baseline = {}, []  # chapters pinned or left out belonged to the other syllabus
    g.exam, g.track, g.class_level, g.exam_date, g.target = stored, body.track, body.class_level, body.exam_date, body.target
    g.dream, g.weekday_hours, g.weekend_hours, g.coaching = body.dream, body.weekday_hours, body.weekend_hours, body.coaching
    g.standing, g.updated_at = standing, utcnow()
    g.edits = {**(g.edits or {}), "day_hours": None}  # the hours just given replace any set day by day
    user.daily_goal_min = round((5 * body.weekday_hours + 2 * body.weekend_hours) / 7 * 60)
    if first or body.apply_standing:
        ticked = set(db.scalars(select(TopicProgress.chapter_id).where(TopicProgress.user_id == user.id)))
        for tid in planner.topics_from_standing(syl, standing):
            cid = tid.rsplit(".", 1)[0]
            if cid not in ticked:  # never overwrite chapters the student has already ticked themselves
                db.add(TopicProgress(user_id=user.id, chapter_id=cid, topic_id=tid, done_at=COVERED_EARLIER))
    db.flush()
    progress = _progress(db, user, syl, tz_offset, today)
    progress.focus_minutes_week = None  # a fresh plan: judge how it's going after a week of it
    plan = planner.build(_plan_goal(g, syl), syl, progress, today)
    g.baseline = plan["baseline"]  # what "on track" means from now on
    db.commit()
    plan["goal"] = _goal_out(g, user)
    return plan


@router.get("/plan")
def get_plan(tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> dict[str, Any] | None:
    """The plan, or null when no goal is set yet (that's a normal state, not an error)."""
    g = _goal(db, user)
    return _built(db, user, g, tz_offset) if g else None


# ---------------------------------------------------------------- editing the plan
class PlanEdit(BaseModel):
    """Changes to the plan made on the plan page itself; anything left out stays as it is."""
    weekday_hours: float | None = Field(None, ge=0, le=16)
    weekend_hours: float | None = Field(None, ge=0, le=16)
    day_hours: list[float] | None = None   # Monday…Sunday; send with clear_day_hours to go back to weekday/weekend
    clear_day_hours: bool = False
    exam_date: date | None = None
    target: str | None = Field(None, max_length=20)
    dream: str | None = Field(None, max_length=120)

    @field_validator("day_hours")
    @classmethod
    def _seven_days(cls, v: list[float] | None) -> list[float] | None:
        if v is not None and (len(v) != 7 or any(not 0 <= h <= 16 for h in v)):
            raise ValueError("Give the hours for all seven days, each between 0 and 16.")
        return v


@router.patch("/plan")
def edit_plan(body: PlanEdit, tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Edit the plan in place: hours (two numbers, or day by day), the exam date, the goal. The plan is rebuilt
    around the change."""
    g = _goal(db, user)
    if g is None:
        raise HTTPException(status_code=404, detail="Set your goal first.")
    today = _today(tz_offset)
    sent = body.model_fields_set
    if body.exam_date is not None:
        if not today < body.exam_date <= today + timedelta(days=3 * 366):
            raise HTTPException(status_code=422, detail="The exam date should be within the next three years.")
        g.exam_date = body.exam_date
    if body.target is not None:
        if body.target not in {t["id"] for t in planner.TARGETS[planner.family(g.exam)]}:
            raise HTTPException(status_code=422, detail="Pick one of the goals offered for this exam.")
        g.target = body.target
    if "dream" in sent:
        g.dream = (body.dream or "").strip() or None
    edits = dict(g.edits or {})
    if body.day_hours is not None:
        if sum(body.day_hours) < 1:
            raise HTTPException(status_code=422, detail="A plan needs at least an hour of study in the week.")
        edits["day_hours"] = [round(h * 2) / 2 for h in body.day_hours]
        g.weekday_hours = round(sum(edits["day_hours"][:5]) / 5, 2)  # the averages, for everything that shows two numbers
        g.weekend_hours = round(sum(edits["day_hours"][5:]) / 2, 2)
    elif body.clear_day_hours or body.weekday_hours is not None or body.weekend_hours is not None:
        edits["day_hours"] = None
        g.weekday_hours = body.weekday_hours if body.weekday_hours is not None else g.weekday_hours
        g.weekend_hours = body.weekend_hours if body.weekend_hours is not None else g.weekend_hours
        if 5 * g.weekday_hours + 2 * g.weekend_hours < 1:
            raise HTTPException(status_code=422, detail="A plan needs at least an hour of study in the week.")
    g.edits, g.updated_at = edits, utcnow()
    weekly = sum(edits["day_hours"]) if edits.get("day_hours") else 5 * g.weekday_hours + 2 * g.weekend_hours
    user.daily_goal_min = round(weekly / 7 * 60)
    db.flush()
    return _built(db, user, g, tz_offset, rebase=bool(sent & {"weekday_hours", "weekend_hours", "day_hours", "clear_day_hours",
                                                              "exam_date"}))


class ChapterEdit(BaseModel):
    action: Literal["next", "unpin", "skip", "restore"]


@router.put("/plan/chapters/{chapter_id}")
def edit_plan_chapter(chapter_id: str, body: ChapterEdit, tz_offset: int = Query(330, ge=-840, le=840),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Change the order of the plan: take a chapter next (ahead of the mentor's order), or leave one out of the
    plan altogether, and undo either."""
    g = _goal(db, user)
    if g is None:
        raise HTTPException(status_code=404, detail="Set your goal first.")
    ch = _chapter(_syllabus(db, user), chapter_id)
    edits = dict(g.edits or {})
    pinned = [c for c in edits.get("pinned") or [] if c != ch.id]
    skipped = [c for c in edits.get("skipped") or [] if c != ch.id]
    if body.action == "next":
        pinned.insert(0, ch.id)  # the latest "do this next" goes first; a chapter taken next is no longer left out
    elif body.action == "skip":
        skipped.append(ch.id)
    edits["pinned"], edits["skipped"] = pinned[:30], skipped
    g.edits, g.updated_at = edits, utcnow()
    db.flush()
    return _built(db, user, g, tz_offset, rebase=body.action in ("skip", "restore"))


class OwnTask(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    minutes: int = Field(30, ge=5, le=600)

    @field_validator("title")
    @classmethod
    def _tidy(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the task a name.")
        return v


MAX_OWN_TASKS = 12  # a day


@router.post("/today/tasks", status_code=201)
def add_task(body: OwnTask, tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Add a task of the student's own to today's list (school homework, a coaching test, anything)."""
    if _goal(db, user) is None:
        raise HTTPException(status_code=404, detail="Set your goal first.")
    today = _today(tz_offset)
    count = db.scalar(select(func.count()).select_from(PlanTask).where(PlanTask.user_id == user.id, PlanTask.day == today))
    if (count or 0) >= MAX_OWN_TASKS:
        raise HTTPException(status_code=422, detail="That's plenty for one day. Finish or remove a task first.")
    db.add(PlanTask(user_id=user.id, day=today, title=body.title, minutes=body.minutes))
    db.commit()
    return get_plan(tz_offset, db, user)["today"]  # type: ignore[index]


@router.delete("/today/tasks/{task_id}")
def remove_task(task_id: int, tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> dict[str, Any]:
    row = db.get(PlanTask, task_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found.")
    db.delete(row)
    db.commit()
    return get_plan(tz_offset, db, user)["today"]  # type: ignore[index]


@router.put("/today-hidden/{task:path}")
def hide_task(task: str, body: Done, tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Take a planned task off today's list ("not today"), or put it back. Nothing is marked done or lost: what
    wasn't studied simply stays in the plan."""
    if _goal(db, user) is None:
        raise HTTPException(status_code=404, detail="Set your goal first.")
    kind = task.partition(":")[0]
    if kind not in planner.KIND_LABEL or len(task) > 190:
        raise HTTPException(status_code=422, detail="Unknown task.")
    today = _today(tz_offset)
    key = f"hide:{task}"
    row = db.scalar(select(PlanCheck).where(PlanCheck.user_id == user.id, PlanCheck.day == today, PlanCheck.task == key))
    if body.done and row is None:
        db.add(PlanCheck(user_id=user.id, day=today, task=key))
    elif not body.done and row is not None:
        db.delete(row)
    db.commit()
    return get_plan(tz_offset, db, user)["today"]  # type: ignore[index]


# ---------------------------------------------------------------- syllabus & progress
@router.get("/syllabus")
def get_syllabus(exam: str | None = None, semester: int | None = Query(None, ge=1, le=8),
                 tz_offset: int = Query(330, ge=-840, le=840),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The syllabus with the student's progress. College: their own subjects, or with ``semester`` the courses the
    plan puts in that semester (to look ahead, or back at something to revise)."""
    syl = _syllabus(db, user, exam)
    mine = list(syl.subjects)
    if syl.is_college and semester is not None:
        whole = _syllabus(db, user, whole=True)
        syl = whole.only(whole.semester_subjects(semester))
    today = _today(tz_offset)
    progress = _progress(db, user, syl, tz_offset, today)
    stock = question_bank.chapter_stock(db)
    in_library = topic_notes.ready(db, syl.library)
    library = syllabus.courses() if syl.library == "college" else {}  # a branch, a GATE paper, placements: subjects are courses
    subjects = []
    for s in syl.subjects:
        units = []
        for subject, unit in syl.units:
            if subject != s:
                continue
            chapters = []
            for ch in syl.chapters:
                if ch.subject != s or ch.unit != unit:
                    continue
                chapters.append({
                    **planner.chapter_summary(ch, progress), "questions": stock.get(s, {}).get(ch.name, 0),
                    "topics": [{"id": t.id, "name": t.name, "done": t.id in progress.done_topics,
                                "video": t.video, "has_notes": bool(t.notes) or t.id in in_library} for t in ch.topics],
                })
            units.append({"name": unit, "chapters": chapters})
        subjects.append({"name": s, "units": units, "about": library.get(s, {}).get("about"),
                         "semester": syl.semester_of(s) if syl.is_college else None, "mine": s in mine})
    topics = sum(len(c.topics) for c in syl.chapters)
    college = None
    if syl.is_college:
        college = {"semester": syllabus.semester_of(user.semester), "viewing": semester, "college": syl.college,
                   "branch": syllabus.BRANCHES[syl.exam], "set_up": user.semester is not None, "my_subjects": mine}
    choices = list(syllabus.get(syl.exam).subjects) if syl.kind == "school" else None  # the subjects there are to take
    return {"exam": syl.exam, "kind": syl.kind, "college": college, "choices": choices, "name": syl.name, "about": syl.about, "subjects": subjects,
            "stats": {"subjects": len(syl.subjects), "chapters": len(syl.chapters), "topics": topics,
                      "hours": round(syl.total_hours), "done_topics": len(progress.done_topics),
                      "questions": sum(n for s in syl.subjects for n in stock.get(s, {}).values())}}


class Done(BaseModel):
    done: bool = True


def _chapter(syl: Syllabus, chapter_id: str):
    ch = syl.by_id.get(chapter_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    return ch


def _set_topic(db: Session, user: User, topic_id: str, done: bool) -> None:
    row = db.scalar(select(TopicProgress).where(TopicProgress.user_id == user.id, TopicProgress.topic_id == topic_id))
    if done and row is None:
        db.add(TopicProgress(user_id=user.id, chapter_id=topic_id.rsplit(".", 1)[0], topic_id=topic_id))
    elif not done and row is not None:
        db.delete(row)


@router.put("/topics/{topic_id}")
def set_topic(topic_id: str, body: Done, tz_offset: int = Query(330, ge=-840, le=840),
              db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    syl = _syllabus(db, user, whole=True)
    found = syl.topic(topic_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Topic not found.")
    _set_topic(db, user, topic_id, body.done)
    db.commit()
    today = _today(tz_offset)
    return planner.chapter_summary(found[0], _progress(db, user, syl, tz_offset, today))


@router.put("/chapters/{chapter_id}/revision")
def set_revision(chapter_id: str, body: Done, tz_offset: int = Query(330, ge=-840, le=840),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Mark (or unmark) today's revision of a chapter."""
    syl = _syllabus(db, user, whole=True)
    ch = _chapter(syl, chapter_id)
    today = _today(tz_offset)
    start = datetime.combine(today, datetime.min.time()) - timedelta(minutes=tz_offset)
    todays = db.scalars(select(ChapterRevision).where(ChapterRevision.user_id == user.id, ChapterRevision.chapter_id == ch.id,
                                                      ChapterRevision.revised_at >= start)).all()
    if body.done and not todays:
        db.add(ChapterRevision(user_id=user.id, chapter_id=ch.id))
    elif not body.done:
        for r in todays:
            db.delete(r)
    db.commit()
    return planner.chapter_summary(ch, _progress(db, user, syl, tz_offset, today))


@router.put("/today/{task:path}")
def check_task(task: str, body: Done, tz_offset: int = Query(330, ge=-840, le=840),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Tick a task in today's plan. Learning ticks its topics and revising logs the revision, so the Prep Hub and
    the plan always agree."""
    g = _goal(db, user)
    if g is None:
        raise HTTPException(status_code=404, detail="Set your goal first.")
    today = _today(tz_offset)
    syl = _syllabus(db, user)
    kind, _, ref = task.partition(":")
    if kind not in ("learn", "practice", "revise", "test", "mock", "custom", "fix") or len(task) > 200:
        raise HTTPException(status_code=422, detail="Unknown task.")
    if kind == "custom":
        own = db.get(PlanTask, int(ref)) if ref.isdigit() else None
        if own is None or own.user_id != user.id:
            raise HTTPException(status_code=404, detail="That task isn't in today's plan any more.")
        own.done = body.done
    elif kind == "learn":
        plan = planner.build(_plan_goal(g, syl), syl, _progress(db, user, syl, tz_offset, today), today)
        item = next((t for t in (plan["today"] or {}).get("tasks", []) if t["key"] == task), None)
        topic_ids = [t["id"] for t in item["topics"]] if item else ([ref] if syl.topic(ref) else [])
        if not topic_ids:
            raise HTTPException(status_code=404, detail="That task isn't in today's plan any more.")
        for tid in topic_ids:
            _set_topic(db, user, tid, body.done)
    elif kind == "revise":
        set_revision(ref, body, tz_offset, db, user)
        return get_plan(tz_offset, db, user)["today"]  # type: ignore[index]
    else:
        row = db.scalar(select(PlanCheck).where(PlanCheck.user_id == user.id, PlanCheck.day == today, PlanCheck.task == task))
        if body.done and row is None:
            db.add(PlanCheck(user_id=user.id, day=today, task=task))
        elif not body.done and row is not None:
            db.delete(row)
    db.commit()
    return get_plan(tz_offset, db, user)["today"]  # type: ignore[index]


@router.get("/topics/{topic_id}")
def topic_detail(topic_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A topic page: its lecture and notes (once added), and what the student captured about it themselves."""
    syl = _syllabus(db, user, whole=True)
    found = syl.topic(topic_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Topic not found.")
    ch, t = found
    words = [w for w in t.name.replace(",", " ").split() if len(w) > 4][:3]
    match = [Note.topic.ilike(f"%{ch.name.split(' ')[0]}%")] + [Note.topic.ilike(f"%{w}%") for w in words]
    mine = db.execute(select(Note.id, Note.topic, Note.session_id, Note.captured_at).join(StudySession)
                      .where(StudySession.user_id == user.id, or_(*match)).order_by(Note.captured_at.desc()).limit(6)).all()
    done = db.scalar(select(TopicProgress.id).where(TopicProgress.user_id == user.id, TopicProgress.topic_id == topic_id))
    return {"id": t.id, "name": t.name, "video": t.video, "done": done is not None,
            "notes_ready": bool(t.notes) or topic_notes.get(db, syl.library, "detailed", t.id) is not None,
            "kind": syl.kind,
            "chapter": {"id": ch.id, "name": ch.name, "subject": ch.subject, "class": ch.cls,
                        "topics": [{"id": x.id, "name": x.name} for x in ch.topics]},
            "your_notes": [{"id": n.id, "topic": n.topic, "session_id": n.session_id,
                            "captured_at": n.captured_at.isoformat() + "Z" if n.captured_at else None} for n in mine],
            "questions": question_bank.chapter_stock(db).get(ch.subject, {}).get(ch.name, 0)}


@router.post("/topics/{topic_id}/notes", dependencies=[Depends(limit("detailed_notes", 20))])
def topic_detailed_notes(topic_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The pre-made detailed notes of a topic, given when the student asks for them. Notes already in the library
    come back at once; a topic nobody has opened yet is written first (and is in the library from then on)."""
    syl = _syllabus(db, user, whole=True)
    found = syl.topic(topic_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Topic not found.")
    ch, t = found
    return library_notes(db, user, syl.library, ch, t)


@router.post("/topics/{topic_id}/notes/report", status_code=204)
def report_topic_notes(topic_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    """A student says this note has a mistake. After a few different students do, it is written again."""
    syl = _syllabus(db, user, whole=True)
    if syl.topic(topic_id) is None:
        raise HTTPException(status_code=404, detail="Topic not found.")
    topic_notes.report(db, syl.library, "detailed", topic_id, user.id)


# ---------------------------------------------------------------- last-day revision
def _test_accuracy(db: Session, user: User) -> dict[tuple[str, str], lastday.Accuracy]:
    """How each chapter went across the student's submitted mocks and chapter tests."""
    out: dict[tuple[str, str], lastday.Accuracy] = {}
    for result in db.scalars(select(MockTest.result).where(MockTest.user_id == user.id, MockTest.status == "submitted")):
        for row in (result or {}).get("chapters") or []:
            subject = "Biology" if row.get("subject") in ("Botany", "Zoology") else row.get("subject")  # NEET's two sections
            acc = out.setdefault((subject, row.get("chapter")), lastday.Accuracy())
            acc.correct += int(row.get("correct") or 0)
            acc.attempted += int(row.get("attempted") or 0)
    return out


PLACE_AT_ONCE = 40  # new lecture topics placed by the model in one request; the rest wait for the next
# a lecture is filed under the chapter it would be revised with, even when no chapter is named after it
LECTURE_NULL = ("the item is not syllabus content at all (screen text, a name, a garbled word). Otherwise choose the "
                "closest chapter, the one a student would revise it with, even when no chapter is named after it "
                "(inequalities go with the algebra chapter they are solved in)")


def _lecture_chapters(db: Session, user: User, syl: Syllabus) -> dict[str, set[str]]:
    """The chapters the student has had lectures on, from the boards they captured: chapter id → the topic ids those
    boards were about. Each board is placed once and the place kept with it: by name when its topic plainly names a
    syllabus topic or chapter, else by the model (all of a request's new topics in one call). While no model can be
    asked, the boards wait unplaced rather than being filed under no chapter."""
    key = f"{syl.exam}:"
    notes = db.scalars(select(Note).join(StudySession).where(StudySession.user_id == user.id, Note.topic.is_not(None))).all()
    pending: dict[tuple[str | None, str], list[Note]] = {}
    for n in notes:
        if (n.chapter_ref or "").startswith(key) or not (n.topic or "").strip():
            continue
        subject = n.subject if n.subject in syl.subjects else None
        found = weak.place(syl, subject, n.topic or "")
        if found:
            n.chapter_ref = key + (found[1].id if found[1] else found[0].id)
        else:
            pending.setdefault((subject, (n.topic or "").strip()), []).append(n)
    asking = list(pending.items())[:PLACE_AT_ONCE]
    asked = weak.ask_chapters(syl, [{"subject": s, "text": t} for (s, t), _ in asking], syl.name,
                              what=f"the topics of {syl.name} lecture boards", null_when=LECTURE_NULL,
                              feature="lecture_place") if asking else None
    if asked is not None:
        for i, (_, boards) in enumerate(asking):
            for n in boards:
                n.chapter_ref = key + (asked[i].id if i in asked else "")
    db.commit()
    out: dict[str, set[str]] = {}
    for n in notes:
        ref = (n.chapter_ref or "")[len(key):] if (n.chapter_ref or "").startswith(key) else ""
        if (placed := syl.topic(ref)) is not None:
            out.setdefault(placed[0].id, set()).add(placed[1].id)
        elif ref in syl.by_id:
            out.setdefault(ref, set())
    return out


class LastDayIn(BaseModel):
    """What the student is revising for, and how they have shaped the list."""
    hours: float = Field(6, ge=1, le=14)
    subject: str | None = Field(None, max_length=40)
    chapters: list[str] = Field(default_factory=list, max_length=120)  # what tomorrow's test covers
    topics: list[str] = Field(default_factory=list, max_length=600)    # …and which topics of those, when known
    include: list[str] = Field(default_factory=list, max_length=120)   # chapters added to today's list by hand
    exclude: list[str] = Field(default_factory=list, max_length=120)   # chapters taken off it
    cover: Literal["important", "studied"] = "important"               # every important chapter, or only studied ones


class LastDayTestIn(LastDayIn):
    count: int = 15  # questions in the test that ends the day


RANK_AHEAD = 6  # chapters next in line whose most-asked topics are found along with the list's, ready to be added


def _last_day(body: LastDayIn, tz_offset: int, db: Session, user: User) -> tuple[dict[str, Any], Syllabus]:
    """The day's list for the student's choices. Which topics of a chapter papers ask most comes from the library;
    the chapters on the list it hasn't ranked yet are ranked now, in one request (services/likely.py)."""
    syl = _syllabus(db, user)
    today = _today(tz_offset)
    goal = _goal(db, user)
    library = syl.library or syl.exam
    progress = _progress(db, user, syl, tz_offset, today)
    shaped = dict(
        hours=body.hours, subject=body.subject, chapter_ids=body.chapters, topic_ids=body.topics, include=body.include,
        exclude=body.exclude, cover=body.cover, accuracy=_test_accuracy(db, user), weak=weak.open_by_chapter(db, user.id),
        lectures=_lecture_chapters(db, user, syl), capsules=topic_notes.ready(db, library, "capsule"),
        exam_date=goal.exam_date if goal and goal.exam == _goal_exam(syl.exam) else None)
    asked = likely.known(db, library, [c.id for c in syl.chapters])
    plan = lastday.build(syl, progress, today, asked=asked, **shaped)
    wanted = [syl.by_id[r["id"]] for r in plan["chapters"] + plan["if_time"][:RANK_AHEAD]]
    if any(c.id not in asked and len(c.topics) >= likely.FEWEST for c in wanted):
        fresh = likely.rank(db, syl, wanted)
        if set(fresh) - set(asked):
            asked.update(fresh)
            plan = lastday.build(syl, progress, today, asked=asked, **shaped)
    return plan, syl


def _final_test(db: Session, user: User, tz_offset: int) -> dict[str, Any] | None:
    """The last-day test the student made today (the latest): its result, or the paper while it is being written."""
    since = datetime.combine(_today(tz_offset), datetime.min.time()) - timedelta(minutes=tz_offset)  # local midnight, in UTC
    tests = db.scalars(select(MockTest).where(MockTest.user_id == user.id, MockTest.pattern == "chapter",
                                              MockTest.created_at >= since).order_by(MockTest.created_at.desc())).all()
    test = next((t for t in tests if (t.config or {}).get("kind") == "revision"), None)
    if test is None:
        return None
    return {"id": test.id, "status": test.status, "progress": test.progress, "score": test.score,
            "max_score": test.max_score, "accuracy": ((test.result or {}).get("total") or {}).get("accuracy"),
            "count": (test.config or {}).get("count")}


@router.get("/last-day")
def last_day(hours: float = Query(6, ge=1, le=14), subject: str | None = None,
             chapters: str | None = Query(None, max_length=4000, description="chapter ids, comma-separated"),
             cover: Literal["important", "studied"] = "important",
             tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> dict[str, Any]:
    """What to revise with one day left: before the exam (everything important in the syllabus), a subject test, or
    a class test on chosen chapters. Built from the syllabus weightage and the student's progress, lectures and test
    results. The order needs no AI; the model is asked only which topics of a chapter papers ask most (once per
    chapter, for everyone) and where a lecture whose topic doesn't name its chapter belongs (once per board)."""
    return last_day_custom(LastDayIn(hours=hours, subject=subject, chapters=[c for c in (chapters or "").split(",") if c],
                                     cover=cover), tz_offset, db, user)


@router.post("/last-day")
def last_day_custom(body: LastDayIn, tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The same list, shaped by the student: the chapters and topics that are coming, everything important or only
    what they have studied, chapters added or taken off."""
    plan, syl = _last_day(body, tz_offset, db, user)
    notes = db.scalars(select(Note).join(StudySession).where(StudySession.user_id == user.id, Note.ai_notes.ilike("%formula%"))).all()
    plan["own"] = {  # the student's own material: the best use of the first half hour
        "redo": db.scalar(select(func.count()).select_from(QuizAttempt).where(QuizAttempt.user_id == user.id,
                                                                              QuizAttempt.needs_redo.is_(True))) or 0,
        "cards_due": db.scalar(select(func.count()).select_from(Flashcard).where(Flashcard.user_id == user.id,
                                                                                 Flashcard.due_at <= utcnow())) or 0,
        "formulas": sum(s["count"] for s in formulas.book(notes)),
        "weak": db.scalar(select(func.count()).select_from(WeakTopic).where(WeakTopic.user_id == user.id, WeakTopic.status == "open")) or 0,
    }
    plan["subjects"] = list(syl.subjects)
    plan["kind"] = syl.kind
    plan["final_test"] = _final_test(db, user, tz_offset)
    plan["test_minutes"] = {n: revision_pattern([{"subject": "", "chapters": [], "count": n}], n, _test_exam(syl)).duration_min
                            for n in lastday.TEST_SIZES}  # how long each size of the final test runs
    return plan


def _test_exam(syl: Syllabus) -> str:
    """Whose questions a last-day test asks, and how it is marked: jee | neet | college | cbse."""
    family = syllabus.family(syl.exam)
    return family if family in ("neet", "college", "cbse") else "jee"


@router.post("/last-day/test", status_code=201, dependencies=[Depends(limit("mock-create", 6))])
def last_day_test(body: LastDayTestIn, tz_offset: int = Query(330, ge=-840, le=840), db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The test that ends the day: questions on the chapters of the day's list only, and in a chapter revised in part,
    only on its listed topics. The list is laid out again from the same choices, so the test covers exactly what the
    page shows. Questions come from the bank; any it lacks are written and checked first, like a chapter test's."""
    if body.count not in lastday.TEST_SIZES:
        raise HTTPException(status_code=422, detail=f"A last-day test has {', '.join(map(str, lastday.TEST_SIZES))} questions.")
    plan, syl = _last_day(body, tz_offset, db, user)
    if not syllabus.has_tests(syl.exam):
        raise HTTPException(status_code=403, detail="Timed tests open in Class 10 and Class 12, the board years.")
    if not plan["chapters"]:
        raise HTTPException(status_code=422, detail="There is nothing on today's list to test yet.")
    config = {"kind": "revision", "parts": lastday.test_parts(plan, body.count), "count": body.count, "exam": _test_exam(syl)}
    mock.finalize_overdue(db, user)
    if db.scalar(select(MockTest.id).where(MockTest.user_id == user.id, MockTest.status == "in_progress")):
        raise HTTPException(status_code=409, detail="Finish or submit the test you're taking before starting another.")
    test = mock.create(db, user, "chapter", config)
    return {"id": test.id, "status": test.status, "title": test.title}


@router.post("/chapters/{chapter_id}/capsule", dependencies=[Depends(limit("detailed_notes", 20))])
def chapter_capsule(chapter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A chapter's last-day capsule from the notes library: must-know formulas, key points, common mistakes and a
    quick self-check. Written (and checked) the first time anyone asks, shared from then on."""
    syl = _syllabus(db, user, whole=True)
    return library_capsule(db, user, syl.library, _chapter(syl, chapter_id))


@router.delete("/goal", status_code=204)
def reset_goal(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    """Start over: removes the goal and all ticked progress. Test results and weak spots are the student's record
    and stay."""
    syl = syllabus.of(user)
    if syl is not None and syl.is_college:
        # only this semester's subjects start over: what was ticked in earlier semesters is the student's record
        own = tuple(f"{syllabus.slug(s)}." for s in syl.subjects)
        for model, column in ((TopicProgress, TopicProgress.topic_id), (ChapterRevision, ChapterRevision.chapter_id)):
            for row in db.scalars(select(model).where(model.user_id == user.id)):
                if getattr(row, column.key).startswith(own):
                    db.delete(row)
        models: tuple = (StudyGoal, PlanCheck, PlanTask)
    else:
        models = (StudyGoal, TopicProgress, ChapterRevision, PlanCheck, PlanTask)
    for model in models:
        db.execute(delete(model).where(model.user_id == user.id))
    db.commit()
