from app.schemas import OrderItemCreate


def calculate_order_total(
    items: list[OrderItemCreate],
) -> int:
    return sum(
        item.quantity * item.unit_price_cents
        for item in items
    )