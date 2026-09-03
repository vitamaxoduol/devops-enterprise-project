from app.domain import calculate_order_total
from app.schemas import OrderItemCreate


def test_calculate_order_total() -> None:
    items = [
        OrderItemCreate(
            sku="BOOK-001",
            quantity=2,
            unit_price_cents=1500,
        ),
        OrderItemCreate(
            sku="HEADSET-001",
            quantity=1,
            unit_price_cents=3000,
        ),
    ]

    result = calculate_order_total(
        items
    )

    assert result == 6000


def test_calculate_order_total_with_single_item() -> None:
    items = [
        OrderItemCreate(
            sku="KEYBOARD-001",
            quantity=3,
            unit_price_cents=2500,
        )
    ]

    result = calculate_order_total(
        items
    )

    assert result == 7500