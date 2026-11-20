from fastapi import APIRouter, Depends

from app.api import (admin, analytics, auth, billing, calls, campus, capture, classes, companion, courses, flashcards, gaps, working, group_sessions, leaderboard, mentors, mock, notes, notifications, ocr, prep,
                     quiz, rooms, seniors, sessions, snap, speech, usage, wait, weak)
from app.core.deps import STUDENT, only_role

# Who may use which part of the API (tests/test_access.py checks every route against this).
# Studying and the AI: students only. A mentor account has its own dashboard and never studies here.
STUDENT_AREAS = (courses, sessions, capture, notes, companion, quiz, flashcards, analytics, rooms, ocr, usage, mock, leaderboard, prep, speech, weak, snap, campus,
                 seniors, classes, wait, gaps, working)
# Both roles: signing in and the account, notifications, payments, and mentoring itself. Inside these, each endpoint
# that belongs to one side says so (require_student / require_mentor), and the admin endpoints need the admin sign-in.
SHARED_AREAS = (auth, billing, mentors, calls, group_sessions, notifications, admin)

api_router = APIRouter(prefix="/api")
for module in STUDENT_AREAS:
    api_router.include_router(module.router, dependencies=[Depends(only_role(STUDENT))])
for module in SHARED_AREAS:
    api_router.include_router(module.router)
api_router.include_router(admin.public)
api_router.include_router(classes.parent)  # a parent's read-only link: its token is the permission
api_router.include_router(mentors.admin)
