import structlog

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import json
import uuid
from datetime import datetime, timezone
from app.events import build_payment_succeeded_event
from app.models import OutboxEvent, Payment

from app.database import get_db
from app.domain import (
    InvalidOrderAmountError,
    OrderNotPayableError,
    validate_order_for_payment,
)
from app.models import Payment
from app.order_client import (
    OrderNotFoundError,
    OrderServiceBadResponseError,
    OrderServiceUnavailableError,
    get_order,
)
from app.processor import process_payment
from app.schemas import (
    PaymentCreate,
    PaymentResponse,
)


router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)

logger = structlog.get_logger()


def get_payment_by_idempotency_key(
    db: Session,
    idempotency_key: str,
) -> Payment | None:
    statement = select(Payment).where(
        Payment.idempotency_key == idempotency_key
    )

    return db.scalar(statement)


def get_payment_by_order_id(
    db: Session,
    order_id: str,
) -> Payment | None:
    statement = select(Payment).where(
        Payment.order_id == order_id
    )

    return db.scalar(statement)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: PaymentCreate,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    db: Session = Depends(get_db),
) -> Payment:
    existing_by_key = (
        get_payment_by_idempotency_key(
            db,
            idempotency_key,
        )
    )

    if existing_by_key is not None:
        if existing_by_key.order_id != payload.order_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Idempotency key has already been "
                    "used for another order."
                ),
            )

        logger.info(
            "payment_idempotency_replay",
            payment_id=existing_by_key.id,
            order_id=existing_by_key.order_id,
        )

        response.status_code = status.HTTP_200_OK

        return existing_by_key

    existing_by_order = get_payment_by_order_id(
        db,
        payload.order_id,
    )

    if existing_by_order is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment already exists for this order.",
        )

    try:
        order = get_order(
            payload.order_id
        )

    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        ) from exc

    except OrderServiceUnavailableError as exc:
        logger.warning(
            "order_service_unavailable",
            order_id=payload.order_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Order Service is temporarily unavailable."
            ),
        ) from exc

    except OrderServiceBadResponseError as exc:
        logger.error(
            "order_service_bad_response",
            order_id=payload.order_id,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Order Service returned an invalid response."
            ),
        ) from exc

    try:
        validate_order_for_payment(
            order
        )

    except OrderNotPayableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order is not payable.",
        ) from exc

    except InvalidOrderAmountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order has an invalid payment amount.",
        ) from exc

    processor_result = process_payment(
        order_id=order.id,
        amount_cents=order.total_amount_cents,
    )

    payment_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())

    occurred_at = datetime.now(timezone.utc)

    payment = Payment(
        id=payment_id,
        order_id=order.id,
        user_id=order.user_id,
        amount_cents=order.total_amount_cents,
        status=processor_result.status,
        provider="mock",
        provider_reference=(
            processor_result.provider_reference
        ),
        idempotency_key=idempotency_key,
    )

    event_payload = (
        build_payment_succeeded_event(
            event_id=event_id,
            payment_id=payment_id,
            order_id=order.id,
            user_id=order.user_id,
            amount_cents=(
                order.total_amount_cents
            ),
            occurred_at=occurred_at,
        )
    )

    outbox_event = OutboxEvent(
        id=event_id,
        aggregate_type="payment",
        aggregate_id=payment_id,
        event_type="payment.succeeded",
        payload=json.dumps(
            event_payload, separators=(",", ":"),
        )
    )

    db.add_all(
        [
            payment,
            outbox_event,
        ]
    )

    try:
        db.commit()
        db.refresh(payment)

    except IntegrityError:
        db.rollback()

        existing_by_key = (
            get_payment_by_idempotency_key(
                db,
                idempotency_key,
            )
        )

        if (
            existing_by_key is not None
            and existing_by_key.order_id
            == payload.order_id
        ):
            response.status_code = status.HTTP_200_OK

            return existing_by_key

        existing_by_order = (
            get_payment_by_order_id(
                db,
                payload.order_id,
            )
        )

        if existing_by_order is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Payment already exists for this order."
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment conflict.",
        )

    except Exception:
        db.rollback()

        logger.exception(
            "payment_creation_failed",
            order_id=payload.order_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create payment.",
        )

    logger.info(
        "payment_succeeded",
        payment_id=payment.id,
        order_id=payment.order_id,
        user_id=payment.user_id,
        amount_cents=payment.amount_cents,
        provider=payment.provider,
    )

    return payment


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
) -> Payment:
    statement = select(Payment).where(
        Payment.id == payment_id
    )

    payment = db.scalar(statement)

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    return payment