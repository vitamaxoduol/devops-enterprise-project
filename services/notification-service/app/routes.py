from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import (
    desc,
    select,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationResponse


router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


@router.get(
    "",
    response_model=list[NotificationResponse],
)
def list_notifications(
    user_id: str | None = None,
    limit: int = Query(
        50,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
) -> list[Notification]:
    statement = select(
        Notification
    )

    if user_id is not None:
        statement = statement.where(
            Notification.user_id == user_id
        )

    statement = (
        statement
        .order_by(
            desc(Notification.created_at)
        )
        .limit(limit)
    )

    return list(
        db.scalars(statement).all()
    )


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
)
def get_notification(
    notification_id: str,
    db: Session = Depends(get_db),
) -> Notification:
    statement = select(
        Notification
    ).where(
        Notification.id == notification_id
    )

    notification = db.scalar(
        statement
    )

    if notification is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Notification not found.",
        )

    return notification