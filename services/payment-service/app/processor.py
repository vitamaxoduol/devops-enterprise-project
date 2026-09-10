import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentProcessorResult:
    status: str
    provider_reference: str


def process_payment(
    order_id: str,
    amount_cents: int,
) -> PaymentProcessorResult:
    if amount_cents <= 0:
        raise ValueError(
            "Payment amount must be greater than zero."
        )

    provider_reference = (
        f"mock_{uuid.uuid4()}"
    )

    return PaymentProcessorResult(
        status="succeeded",
        provider_reference=provider_reference,
    )