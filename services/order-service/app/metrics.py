from prometheus_client import (
    Counter,
    Histogram,
)


ORDERS_CREATED_TOTAL = Counter(
    "orders_created_total",
    "Total number of orders created.",
)


ORDER_VALUE_CENTS = Histogram(
    "order_value_cents",
    "Order value in minor currency units.",
    buckets=(
        500,
        1000,
        2500,
        5000,
        10000,
        25000,
        50000,
        100000,
    ),
)


ORDER_UPSTREAM_FAILURES_TOTAL = Counter(
    "order_upstream_failures_total",
    "Order Service upstream failures.",
    [
        "reason",
    ],
)