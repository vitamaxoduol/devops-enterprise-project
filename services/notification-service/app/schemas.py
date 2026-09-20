from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)


class PaymentSucceededData(BaseModel):
    payment_id: str
    order_id: str
    user_id: str
    amount_cents: int


class PaymentSucceededEvent(BaseModel):
    event_id: str

    event_type: Literal[
        "payment.succeeded"
    ]

    schema_version: Literal[1]

    occurred_at: datetime

    data: PaymentSucceededData


class NotificationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    event_id: str
    event_type: str

    user_id: str
    order_id: str
    payment_id: str

    amount_cents: int

    channel: str
    message: str

    created_at: datetime