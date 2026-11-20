from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.course import Course
from app.models.session import StudySession
from app.models.user import User
from app.schemas.course import CourseIn, CourseOut, CourseUpdate

router = APIRouter(prefix="/courses", tags=["courses"])


def _owned(db: Session, user: User, course_id: int) -> Course:
    c = db.get(Course, course_id)
    if not c or c.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Course not found")
    return c


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(Course, func.count(StudySession.id))
        .outerjoin(StudySession, StudySession.course_id == Course.id)
        .where(Course.owner_id == user.id)
        .group_by(Course.id)
        .order_by(Course.created_at.desc())
    ).all()
    out = []
    for course, count in rows:
        item = CourseOut.model_validate(course)
        item.session_count = count
        out.append(item)
    return out


@router.post("", response_model=CourseOut, status_code=201)
def create_course(body: CourseIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = Course(owner_id=user.id, **body.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, body: CourseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = _owned(db, user, course_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = _owned(db, user, course_id)
    db.execute(update(StudySession).where(StudySession.course_id == course.id).values(course_id=None))
    db.delete(course)
    db.commit()
