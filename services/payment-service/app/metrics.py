from prometheus_client import Counter


PAYMENTS_SUCCEEDED_TOTAL = Counter(
    "payments_succeeded_total",
    "Total successful payments.",
)


PAYMENT_IDEMPOTENCY_REPLAYS_TOTAL = Counter(
    "payment_idempotency_replays_total",
    "Total payment idempotency replays.",
)


PAYMENT_UPSTREAM_FAILURES_TOTAL = Counter(
    "payment_upstream_failures_total",
    "Payment upstream dependency failures.",
    [
        "reason",
    ],
)


OUTBOX_EVENTS_CREATED_TOTAL = Counter(
    "outbox_events_created_total",
    "Total events written to the outbox.",
)