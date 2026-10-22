import structlog

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserResponse
from app.metrics import USERS_CREATED_TOTAL


router = APIRouter(prefix="/users", tags=["users"])
logger = structlog.get_logger()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    user = User(
        name=payload.name,
        email=payload.email,
    )

    db.add(user)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    db.refresh(user)

    # Increment only after the user was successfully created.
    USERS_CREATED_TOTAL.inc()

    logger.info("user_created", user_id=user.id)

    return user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
) -> User:
    statement = select(User).where(User.id == user_id)

    user = db.scalar(statement)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return user
