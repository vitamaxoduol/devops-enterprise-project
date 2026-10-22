from contextvars import ContextVar
from uuid import uuid4


_request_id: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(
    request_id: str,
):
    return _request_id.set(
        request_id
    )


def reset_request_id(
    token,
) -> None:
    _request_id.reset(
        token
    )


def resolve_request_id(
    incoming: str | None,
) -> str:
    if (
        incoming
        and 1 <= len(incoming) <= 128
    ):
        return incoming

    return str(
        uuid4()
    )