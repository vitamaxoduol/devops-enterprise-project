import pytest

from app.processor import process_payment


def test_process_payment_succeeds() -> None:
    result = process_payment(
        order_id="11111111-1111-1111-1111-111111111111",
        amount_cents=6000,
    )

    assert result.status == "succeeded"
    assert result.provider_reference.startswith(
        "mock_"
    )


def test_process_payment_rejects_zero_amount() -> None:
    with pytest.raises(
        ValueError
    ):
        process_payment(
            order_id=(
                "11111111-1111-1111-1111-111111111111"
            ),
            amount_cents=0,
        )