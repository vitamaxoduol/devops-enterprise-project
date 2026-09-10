from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    order_id: str = Field(
        min_length=1,
        max_length=36,
    )


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    user_id: str
    amount_cents: int
    status: str
    provider: str
    provider_reference: str
    created_at: datetime


class OrderLookupResponse(BaseModel):
    id: str
    user_id: str
    status: str
    total_amount_cents: int