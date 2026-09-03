import httpx

from app.config import settings
from app.schemas import UserLookupResponse


class UserNotFoundError(Exception):
    pass


class UserServiceUnavailableError(Exception):
    pass


class UserServiceBadResponseError(Exception):
    pass


def get_user(
    user_id: str,
    client: httpx.Client | None = None,
) -> UserLookupResponse:
    owns_client = client is None

    if client is None:
        client = httpx.Client(
            base_url=settings.user_service_url,
            timeout=settings.user_service_timeout_seconds,
        )

    try:
        response = client.get(
            f"/users/{user_id}",
        )

        if response.status_code == 404:
            raise UserNotFoundError(
                f"User {user_id} does not exist."
            )

        if response.status_code >= 500:
            raise UserServiceUnavailableError(
                "User Service returned a server error."
            )

        if response.status_code >= 400:
            raise UserServiceBadResponseError(
                f"Unexpected User Service response: "
                f"{response.status_code}"
            )

        try:
            return UserLookupResponse.model_validate(
                response.json()
            )

        except Exception as exc:
            raise UserServiceBadResponseError(
                "User Service returned an invalid response."
            ) from exc

    except (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
    ) as exc:
        raise UserServiceUnavailableError(
            "User Service is unavailable."
        ) from exc

    finally:
        if owns_client:
            client.close()


def user_service_is_ready() -> bool:
    try:
        with httpx.Client(
            base_url=settings.user_service_url,
            timeout=settings.user_service_timeout_seconds,
        ) as client:
            response = client.get(
                "/health/ready"
            )

        return response.status_code == 200

    except httpx.HTTPError:
        return False