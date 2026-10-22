from datetime import datetime, timezone
from opentelemetry.propagate import (
    inject,
)

from app.request_context import (
    get_request_id,
)


def build_payment_succeeded_event(
    *,
    event_id: str,
    payment_id: str,
    order_id: str,
    user_id: str,
    amount_cents: int,
    occurred_at: datetime | None = None,
) -> dict:
    timestamp = (
        occurred_at
        or datetime.now(timezone.utc)
    )

    trace_context: dict[str, str] = {}

    inject(
        trace_context
    )

    return {
        "event_id": event_id,
        "event_type": "payment.succeeded",
        "schema_version": 1,
        "occurred_at": timestamp.isoformat(),
        "correlation_id": (
            get_request_id()
        ),
        "trace_context": (
            trace_context
        ),
        "data": {
            "payment_id": payment_id,
            "order_id": order_id,
            "user_id": user_id,
            "amount_cents": amount_cents,
        },
    }