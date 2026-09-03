import structlog

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.domain import calculate_order_total
from app.models import Order, OrderItem
from app.schemas import OrderCreate, OrderResponse
from app.user_client import (
    UserNotFoundError,
    UserServiceBadResponseError,
    UserServiceUnavailableError,
    get_user,
)


router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

logger = structlog.get_logger()


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
) -> Order:
    try:
        user = get_user(
            payload.user_id
        )

    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from exc

    except UserServiceUnavailableError as exc:
        logger.warning(
            "user_service_unavailable",
            user_id=payload.user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User Service is temporarily unavailable.",
        ) from exc

    except UserServiceBadResponseError as exc:
        logger.error(
            "user_service_bad_response",
            user_id=payload.user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="User Service returned an invalid response.",
        ) from exc

    total_amount_cents = calculate_order_total(
        payload.items
    )

    order = Order(
        user_id=user.id,
        status="pending_payment",
        total_amount_cents=total_amount_cents,
    )

    for item in payload.items:
        line_total_cents = (
            item.quantity
            * item.unit_price_cents
        )

        order.items.append(
            OrderItem(
                sku=item.sku,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                line_total_cents=line_total_cents,
            )
        )

    db.add(order)

    try:
        db.commit()
        db.refresh(order)

    except Exception:
        db.rollback()

        logger.exception(
            "order_creation_failed",
            user_id=payload.user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create order.",
        )

    logger.info(
        "order_created",
        order_id=order.id,
        user_id=order.user_id,
        total_amount_cents=order.total_amount_cents,
        item_count=len(order.items),
    )

    return order


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
) -> Order:
    statement = (
        select(Order)
        .options(
            selectinload(Order.items)
        )
        .where(
            Order.id == order_id
        )
    )

    order = db.scalar(statement)

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    return order