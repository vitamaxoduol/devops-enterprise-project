from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    sku: str = Field(
        min_length=1,
        max_length=100,
    )

    quantity: int = Field(
        gt=0,
        le=100,
    )

    unit_price_cents: int = Field(
        ge=0,
    )


class OrderCreate(BaseModel):
    user_id: str

    items: list[OrderItemCreate] = Field(
        min_length=1,
        max_length=100,
    )


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    status: str
    total_amount_cents: int
    created_at: datetime

    items: list[OrderItemResponse]


class UserLookupResponse(BaseModel):
    id: str
    name: str
    email: str