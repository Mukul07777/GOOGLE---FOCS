from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services import mock, usage

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
def get_usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The student's AI allowance (a study day + a weekly cap, under a 30-day fair-use ceiling) and full mock tests
    left this week."""
    return {**usage.status(db, user), "mocks": mock.quota(db, user)}
