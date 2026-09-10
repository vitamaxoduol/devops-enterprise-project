import pytest

from app.domain import (
    InvalidOrderAmountError,
    OrderNotPayableError,
    validate_order_for_payment,
)
from app.schemas import OrderLookupResponse


def test_pending_order_is_payable() -> None:
    order = OrderLookupResponse(
        id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        status="pending_payment",
        total_amount_cents=6000,
    )

    validate_order_for_payment(order)


def test_cancelled_order_is_not_payable() -> None:
    order = OrderLookupResponse(
        id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        status="cancelled",
        total_amount_cents=6000,
    )

    with pytest.raises(
        OrderNotPayableError
    ):
        validate_order_for_payment(order)


def test_zero_value_order_is_not_payable() -> None:
    order = OrderLookupResponse(
        id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        status="pending_payment",
        total_amount_cents=0,
    )

    with pytest.raises(
        InvalidOrderAmountError
    ):
        validate_order_for_payment(order)