from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import EXAM_TARGETS
from app.schemas.common import ORM, UTCDateTime

ExamTarget = Literal["jee", "neet", "ssc_cgl", "upsc", "gate", "ca", "cbse", "coding", "college",
                      "college_cse", "college_it", "college_ece", "college_ee", "college_me", "college_ce", "college_ai", "college_che", "college_bt",
                      "gate_cs", "gate_da", "gate_ec", "gate_ee", "gate_me", "gate_ce", "cbse_1", "cbse_2", "cbse_3", "cbse_4",
                      "cbse_5", "cbse_6", "cbse_7", "cbse_8", "cbse_9", "cbse_10", "cbse_11", "cbse_12", "other"]
assert set(ExamTarget.__args__) == set(EXAM_TARGETS)
College = Literal["iitd", "iiitd", "dtu", "nsut", "ggsipu", "aktu", "other"]


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    exam_target: ExamTarget = "jee"
    class_level: str | None = Field(default=None, max_length=40)
    accepted_terms: bool = False  # Terms + Privacy (and guardian consent for minors), ticked at sign-up
    role: Literal["student", "mentor"] = "student"  # a mentor account: its application and approval come next
    # college students: whose semester plan they follow, and the semester they are in
    college: College | None = None
    semester: int | None = Field(default=None, ge=1, le=8)

    @field_validator("full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class LoginIn(BaseModel):
    # not EmailStr: signing in needs no format check (an unknown address just fails), and a strict one
    # shows students a validator's wording instead of "Incorrect email or password"
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    plan: str | None = "free"
    exam_target: str | None = "jee"
    class_level: str | None = None
    daily_goal_min: int | None = 60
    show_on_leaderboard: bool | None = True
    created_at: UTCDateTime | None = None
    college: str | None = None
    semester: int | None = None
    subjects: list[str] | None = None
    language: str | None = None
    pro_until: UTCDateTime | None = None
    role: str | None = "student"


class LoginCodeOut(BaseModel):
    """The right password, and a code on its way to the account's email: the second step of signing in."""
    code_required: bool = True
    challenge: str
    sent_to: str              # the address, partly hidden
    resend_after: int         # seconds


class LoginCodeIn(BaseModel):
    challenge: str = Field(min_length=20, max_length=1000)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class LoginResendIn(BaseModel):
    challenge: str = Field(min_length=20, max_length=1000)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    created: bool = False  # a new account (Google sign-in makes one on the sign-up page): goal set-up comes next


class GoogleIn(BaseModel):
    """The ID token from Google's button. On the sign-up page also the choices a new account needs; on the sign-in
    page none, and an email with no account is sent to sign up rather than given one without the Terms."""
    credential: str = Field(min_length=20, max_length=4096)
    accepted_terms: bool = False
    exam_target: ExamTarget | None = None  # required for a new account: never assumed
    college: College | None = None
    semester: int | None = Field(default=None, ge=1, le=8)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=80)
    exam_target: ExamTarget | None = None
    class_level: str | None = Field(default=None, max_length=40)
    daily_goal_min: int | None = Field(default=None, ge=10, le=720)
    show_on_leaderboard: bool | None = None
    college: College | None = None
    semester: int | None = Field(default=None, ge=1, le=8)
    language: Literal["en", "hinglish", "hi"] | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AccountDelete(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(max_length=10)


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str = Field(min_length=20, max_length=2000)
    new_password: str = Field(min_length=8, max_length=128)
