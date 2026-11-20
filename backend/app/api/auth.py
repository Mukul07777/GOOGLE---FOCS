import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api import rooms
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import client_ip, guard, limit, record
from app.core.security import (
    create_access_token,
    create_login_challenge,
    create_reset_token,
    hash_password,
    read_login_challenge,
    read_reset_token,
    reset_token_matches,
    verify_password,
)
from app.models._util import utcnow
from app.models.prep import StudyGoal
from app.models.user import User
from app.schemas.auth import (
    AccountDelete,
    GoogleIn,
    LoginCodeIn,
    LoginCodeOut,
    LoginResendIn,
    ForgotPassword,
    LoginIn,
    PasswordChange,
    ProfileUpdate,
    RegisterIn,
    ResetPassword,
    TokenOut,
    UserOut,
)
from app.services import account, google_auth, login_code, mailer, syllabus

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id, version=user.token_version or 0), user=UserOut.model_validate(user))


def _college(user: User, college: str | None, semester: int | None, class_level: str | None) -> None:
    """A B.Tech student: whose semester plan they follow, and their semester."""
    if syllabus.is_college(syllabus.exam_of(user.exam_target)):
        user.college, user.semester = college, semester
        user.class_level = f"Semester {semester}" if semester else class_level


# A class signing up together shares one address, so the per-minute limit is generous; the hourly one stops a script
# from making thousands of free accounts (each with its own AI allowance) from one machine.
SIGNUPS_PER_ADDRESS_HOUR = 60
# exams the sign-up page no longer offers (utils.ts SIGNUP_EXAMS); students already on them keep their plans
CLOSED_SIGNUP_EXAMS = {"upsc", "gate", "ca"}


@router.post("/register", response_model=TokenOut | LoginCodeOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(limit("register", 30))])
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not body.accepted_terms:  # the page's checkbox is not enough: a direct API call must agree too (and a minor's guardian)
        raise HTTPException(status_code=422, detail="Accept the Terms and Privacy Policy to create an account.")
    if body.role == "student" and body.exam_target in CLOSED_SIGNUP_EXAMS:
        raise HTTPException(status_code=422, detail="Focs doesn't take new sign-ups for this exam. Pick another one.")
    signups = f"signups:{client_ip(request)}"
    guard(signups, SIGNUPS_PER_ADDRESS_HOUR, 3600)
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Try signing in.")
    user = User(email=email, full_name=body.full_name, hashed_pw=hash_password(body.password),
                exam_target=body.exam_target, class_level=body.class_level, plan="free", is_active=True,
                consent_at=utcnow() if body.accepted_terms else None, role=body.role)
    if body.role == "mentor":
        user.exam_target, user.class_level = None, None  # a mentor isn't preparing for anything: their exam is in the application
    else:
        _college(user, body.college, body.semester, body.class_level)
    db.add(user)
    db.commit()
    db.refresh(user)
    record(signups)
    if login_code.needed():  # the address must be the person's own: no account opens until its code is typed
        return _send_login_code(db, user)
    return _token_response(user)


# A whole classroom or event hall signs in from one public address, so the per-address limit is generous; password
# guessing is stopped per email instead (failed attempts only).
LOGIN_FAILS_PER_EMAIL = 8
LOGIN_FAIL_WINDOW_S = 15 * 60


@router.post("/login", response_model=TokenOut | LoginCodeOut, dependencies=[Depends(limit("login", 60))])
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    guard(f"login-fail:{email}", LOGIN_FAILS_PER_EMAIL, LOGIN_FAIL_WINDOW_S)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user and email == settings.ADMIN_USERNAME.strip().lower():
        # the admin ID typed into the student sign-in: point to the admin panel (its password is never checked here)
        raise HTTPException(status_code=409, detail="That's the admin ID. The admin panel has its own sign-in at /admin.")
    if not user or not verify_password(body.password, user.hashed_pw):
        record(f"login-fail:{email}")
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if user.is_active is False:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")
    if not login_code.needed():
        return _token_response(user)
    return _send_login_code(db, user)  # the second step: the code from their email


def _send_login_code(db: Session, user: User) -> LoginCodeOut:
    code = login_code.start(user)
    db.commit()
    if not login_code.send_in_background(user, code):
        raise HTTPException(status_code=502, detail="We couldn't email your sign-in code just now. Try again in a minute.")
    return LoginCodeOut(challenge=create_login_challenge(user.id, user.token_version or 0, login_code.CODE_MINUTES),
                        sent_to=login_code.hint(user.email), resend_after=login_code.RESEND_AFTER_S)


def _challenged(db: Session, challenge: str) -> User:
    claims = read_login_challenge(challenge)
    user = db.get(User, claims[0]) if claims else None
    if not user or user.is_active is False or claims[1] != (user.token_version or 0):
        raise HTTPException(status_code=401, detail="This sign-in has expired. Enter your email and password again.")
    return user


@router.post("/login/verify", response_model=TokenOut, dependencies=[Depends(limit("login-code", 20))])
def login_verify(body: LoginCodeIn, db: Session = Depends(get_db)):
    """The second step: the 6-digit code from the email. Five wrong codes end this sign-in."""
    user = _challenged(db, body.challenge)
    problem = login_code.confirm(user, body.code)
    db.commit()
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    return _token_response(user)


@router.post("/login/resend", response_model=LoginCodeOut, dependencies=[Depends(limit("login-resend", 5))])
def login_resend(body: LoginResendIn, db: Session = Depends(get_db)):
    user = _challenged(db, body.challenge)
    if (wait := login_code.wait_before_resend(user)) > 0:
        raise HTTPException(status_code=429, detail=f"Wait {wait} seconds before asking for another code.")
    return _send_login_code(db, user)


@router.post("/google", response_model=TokenOut, dependencies=[Depends(limit("google", 30))])
def google(body: GoogleIn, request: Request, db: Session = Depends(get_db)):
    """Continue with Google. A verified Google email that already has a Focs account signs in to it (a password
    account too: the password keeps working). A new email gets a student account only from the sign-up page, where
    the exam is picked and the Terms are accepted; from the sign-in page it is told to sign up first (404)."""
    try:
        claims = google_auth.verify(body.credential)
    except google_auth.GoogleTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    email = str(claims["email"]).strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user:
        if user.is_active is False:
            raise HTTPException(status_code=403, detail="This account has been deactivated.")
        return _token_response(user)
    if not body.accepted_terms:
        raise HTTPException(status_code=404, detail="No Focs account uses this Google email yet. Create one: pick your exam, "
                                                    "accept the Terms, then continue with Google.")
    if body.exam_target is None:  # an account made as JEE by default became a JEE student who never chose it
        raise HTTPException(status_code=422, detail="Pick what you're preparing for, then continue with Google.")
    if body.exam_target in CLOSED_SIGNUP_EXAMS:
        raise HTTPException(status_code=422, detail="Focs doesn't take new sign-ups for this exam. Pick another one.")
    signups = f"signups:{client_ip(request)}"
    guard(signups, SIGNUPS_PER_ADDRESS_HOUR, 3600)
    name = " ".join(str(claims.get("name") or email.split("@")[0]).split())[:80] or "Student"
    # no password of its own: a random one nobody knows (forgot-password sets a real one if the student wants it)
    user = User(email=email, full_name=name, hashed_pw=hash_password(secrets.token_urlsafe(32)), exam_target=body.exam_target,
                plan="free", is_active=True, consent_at=utcnow(), role="student")
    _college(user, body.college, body.semester, None)
    db.add(user)
    db.commit()
    db.refresh(user)
    record(signups)
    return _token_response(user).model_copy(update={"created": True})


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(limit("refresh", 30))])
def refresh(user: User = Depends(get_current_user)):
    """A fresh 7-day token for a signed-in student: people who use Focs regularly never get logged out mid-study."""
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    before = syllabus.exam_of(user.exam_target), user.college, user.semester
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    exam = syllabus.exam_of(user.exam_target)
    if exam != before[0] and not syllabus.is_college(exam):
        user.subjects = None  # the subjects picked were another exam's
    if syllabus.is_school(exam):
        user.class_level = f"Class {syllabus.SCHOOL[exam]}"
    if syllabus.is_college(exam):
        if (exam, user.college, user.semester) != before:
            user.subjects = None  # another branch, college or semester: that plan's courses, until they pick again
            goal = db.scalar(select(StudyGoal).where(StudyGoal.user_id == user.id, StudyGoal.exam == "college"))
            if goal is not None:  # the plan carries on with the new subjects; "on track" is measured from now
                goal.baseline, goal.edits = [], {**(goal.edits or {}), "pinned": [], "skipped": []}
                goal.class_level = str(user.semester) if user.semester else goal.class_level
        if user.semester:
            user.class_level = f"Semester {user.semester}"
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", response_model=TokenOut, dependencies=[Depends(limit("password", 6))])
def change_password(body: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """New password; every other signed-in device is signed out. This one gets a fresh token."""
    if not verify_password(body.current_password, user.hashed_pw):
        raise HTTPException(status_code=400, detail="Your current password is incorrect.")
    user.hashed_pw = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    return _token_response(user)


@router.get("/export", dependencies=[Depends(limit("export", 6))])
def export_my_data(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Everything Focs stores about the student, as one JSON file."""
    return JSONResponse(account.export(db, user),
                        headers={"Content-Disposition": 'attachment; filename="focs-my-data.json"'})


@router.post("/delete-account", status_code=204, dependencies=[Depends(limit("delete-account", 5))])
async def delete_account(body: AccountDelete, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.confirm != "DELETE":
        raise HTTPException(status_code=422, detail="Type DELETE to confirm.")
    if not verify_password(body.password, user.hashed_pw):
        raise HTTPException(status_code=400, detail="That password is incorrect.")
    for code in await run_in_threadpool(account.delete_everything, db, user):
        await rooms.hub.broadcast(code, {"type": "closed"})


@router.post("/forgot-password", status_code=204, dependencies=[Depends(limit("forgot", 5))])
def forgot_password(body: ForgotPassword, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Always 204, so the form can't be used to find out who has an account. The email goes out in the background."""
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if user and mailer.configured():
        link = f"{settings.APP_URL.rstrip('/')}/reset-password?token={create_reset_token(user.id, user.hashed_pw)}"
        background.add_task(mailer.send_password_reset, user.email, user.full_name, link)


@router.post("/reset-password", status_code=204, dependencies=[Depends(limit("reset", 10))])
def reset_password(body: ResetPassword, db: Session = Depends(get_db)):
    claims = read_reset_token(body.token)
    user = db.get(User, claims[0]) if claims else None
    if not user or not reset_token_matches(claims[1], user.hashed_pw):  # expired, forged, or already used
        raise HTTPException(status_code=400, detail="This reset link has expired or was already used. Ask for a new one.")
    user.hashed_pw = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1  # whoever knew the old password is signed out
    db.commit()
