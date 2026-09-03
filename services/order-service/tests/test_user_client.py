import httpx
import pytest

from app.user_client import (
    UserNotFoundError,
    UserServiceUnavailableError,
    get_user,
)


def test_get_user_success() -> None:
    user_id = (
        "11111111-1111-1111-1111-111111111111"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == (
            f"/users/{user_id}"
        )

        return httpx.Response(
            status_code=200,
            json={
                "id": user_id,
                "name": "Test User",
                "email": "test@example.com",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        base_url="http://user-service:8000",
        transport=transport,
    ) as client:
        user = get_user(
            user_id,
            client=client,
        )

    assert user.id == user_id
    assert user.name == "Test User"
    assert user.email == "test@example.com"


def test_get_user_not_found() -> None:
    user_id = (
        "11111111-1111-1111-1111-111111111111"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={
                "detail": "User not found."
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        base_url="http://user-service:8000",
        transport=transport,
    ) as client:
        with pytest.raises(
            UserNotFoundError
        ):
            get_user(
                user_id,
                client=client,
            )


def test_get_user_timeout() -> None:
    user_id = (
        "11111111-1111-1111-1111-111111111111"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "Timed out",
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        base_url="http://user-service:8000",
        transport=transport,
    ) as client:
        with pytest.raises(
            UserServiceUnavailableError
        ):
            get_user(
                user_id,
                client=client,
            )