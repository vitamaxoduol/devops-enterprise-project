from prometheus_client import Counter


USERS_CREATED_TOTAL = Counter(
    "users_created_total",
    "Total number of users created.",
)