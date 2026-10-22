from fastapi import FastAPI, Request
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
)

from app.request_context import (
    reset_request_id,
    resolve_request_id,
    set_request_id,
)


def install_request_context_middleware(
    app: FastAPI,
) -> None:

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next,
    ):
        request_id = resolve_request_id(
            request.headers.get(
                "X-Request-ID"
            )
        )

        clear_contextvars()

        bind_contextvars(
            request_id=request_id
        )

        token = set_request_id(
            request_id
        )

        try:
            response = await call_next(
                request
            )

            response.headers[
                "X-Request-ID"
            ] = request_id

            return response

        finally:
            reset_request_id(
                token
            )