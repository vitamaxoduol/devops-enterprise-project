import httpx
import pytest

from app.order_client import (
    OrderNotFoundError,
    OrderServiceUnavailableError,
    get_order,
)


def test_get_order_success() -> None:
    order_id = (
        "11111111-1111-1111-1111-111111111111"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == (
            f"/orders/{order_id}"
        )

        return httpx.Response(
            status_code=200,
            json={
                "id": order_id,
                "user_id": (
                    "22222222-2222-2222-2222-222222222222"
                ),
                "status": "pending_payment",
                "total_amount_cents": 6000,
                "created_at": "2026-09-03T10:00:00Z",
                "items": [],
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        base_url="http://order-service:8000",
        transport=transport,
    ) as client:
        order = get_order(
            order_id,
            client=client,
        )

    assert order.id == order_id
    assert order.status == "pending_payment"
    assert order.total_amount_cents == 6000


def test_get_order_not_found() -> None:
    order_id = (
        "11111111-1111-1111-1111-111111111111"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={
                "detail": "Order not found."
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        base_url="http://order-service:8000",
        transport=transport,
    ) as client:
        with pytest.raises(
            OrderNotFoundError
        ):
            get_order(
                order_id,
                client=client,
            )


def test_get_order_timeout() -> None:
    order_id = (
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
        base_url="http://order-service:8000",
        transport=transport,
    ) as client:
        with pytest.raises(
            OrderServiceUnavailableError
        ):
            get_order(
                order_id,
                client=client,
            )