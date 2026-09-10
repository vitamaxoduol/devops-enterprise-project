from app.schemas import OrderLookupResponse


class OrderNotPayableError(Exception):
    pass


class InvalidOrderAmountError(Exception):
    pass


def validate_order_for_payment(
    order: OrderLookupResponse,
) -> None:
    if order.status != "pending_payment":
        raise OrderNotPayableError(
            f"Order status is {order.status}."
        )

    if order.total_amount_cents <= 0:
        raise InvalidOrderAmountError(
            "Order amount must be greater than zero."
        )