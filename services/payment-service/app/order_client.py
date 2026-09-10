import httpx

from app.config import settings
from app.schemas import OrderLookupResponse


class OrderNotFoundError(Exception):
    pass


class OrderServiceUnavailableError(Exception):
    pass


class OrderServiceBadResponseError(Exception):
    pass


def get_order(
    order_id: str,
    client: httpx.Client | None = None,
) -> OrderLookupResponse:
    owns_client = client is None

    if client is None:
        client = httpx.Client(
            base_url=settings.order_service_url,
            timeout=settings.order_service_timeout_seconds,
        )

    try:
        response = client.get(
            f"/orders/{order_id}"
        )

        if response.status_code == 404:
            raise OrderNotFoundError(
                f"Order {order_id} does not exist."
            )

        if response.status_code >= 500:
            raise OrderServiceUnavailableError(
                "Order Service returned a server error."
            )

        if response.status_code >= 400:
            raise OrderServiceBadResponseError(
                f"Unexpected Order Service response: "
                f"{response.status_code}"
            )

        try:
            return OrderLookupResponse.model_validate(
                response.json()
            )

        except Exception as exc:
            raise OrderServiceBadResponseError(
                "Order Service returned an invalid response."
            ) from exc

    except (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
    ) as exc:
        raise OrderServiceUnavailableError(
            "Order Service is unavailable."
        ) from exc

    finally:
        if owns_client:
            client.close()


def order_service_is_ready() -> bool:
    try:
        with httpx.Client(
            base_url=settings.order_service_url,
            timeout=settings.order_service_timeout_seconds,
        ) as client:
            response = client.get(
                "/health/ready"
            )

        return response.status_code == 200

    except httpx.HTTPError:
        return False