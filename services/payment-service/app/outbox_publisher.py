import time
import json
from datetime import datetime, timezone

import boto3
import structlog
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
from sqlalchemy import (
    select,
    func
)

from app.config import settings
from app.database import SessionLocal
from app.logging import configure_logging
from app.models import OutboxEvent

from opentelemetry import trace
from opentelemetry.propagate import (
    extract,
    inject,
)
from opentelemetry.trace import (
    SpanKind,
)

from app.telemetry import (
    configure_telemetry,
)
from prometheus_client import (
    Counter,
    Gauge,
    start_http_server,
)


configure_logging(
    "payment-event-publisher"
    )

logger = structlog.get_logger()

OUTBOX_PUBLISH_TOTAL = Counter(
    "outbox_publish_total",
    "Outbox publication attempts.",
    [
        "result",
    ],
)


OUTBOX_PENDING = Gauge(
    "outbox_pending_events",
    "Number of unpublished outbox events.",
)


def create_sqs_client():
    return boto3.client(
        "sqs",
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
    )


def get_queue_url(client) -> str:
    response = client.get_queue_url(
        QueueName=(
            settings.payment_events_queue_name
        )
    )

    return response["QueueUrl"]


def publish_next_event(
    client,
    queue_url: str,
) -> bool:
    with SessionLocal() as db:
        statement = (
            select(OutboxEvent)
            .where(
                OutboxEvent.published_at.is_(None)
            )
            .order_by(
                OutboxEvent.created_at
            )
            .limit(1)
        )

        event = db.scalar(statement)

        if event is None:
            return False

        try:
            payload = json.loads(
                event.payload
            )

            parent_context = extract(
                payload.get(
                    "trace_context",
                    {},
                )
            )

            with tracer.start_as_current_span(
                "payment.succeeded publish",
                context=parent_context,
                kind=SpanKind.PRODUCER,
            ) as span:

                span.set_attribute(
                    "messaging.system",
                    "aws_sqs",
                )

                span.set_attribute(
                    "messaging.destination.name",
                    settings.payment_events_queue_name,
                )

                span.set_attribute(
                    "event.id",
                    event.id,
                )

                outgoing_context: dict[str, str] = {}

                inject(
                    outgoing_context
                )

                payload[
                    "trace_context"
                ] = outgoing_context

                client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(
                        payload,
                        separators=(",", ":"),
                    ),
                )

        except (
            BotoCoreError,
            ClientError,
        ):
            event.publish_attempts += 1
            db.commit()

            OUTBOX_PUBLISH_TOTAL.labels(
                result="failure"
            ).inc()

            logger.exception(
                "outbox_publish_failed",
                event_id=event.id,
                event_type=event.event_type,
                attempts=event.publish_attempts,
            )

            raise

        event.publish_attempts += 1

        event.published_at = datetime.now(
            timezone.utc
        )

        db.commit()

        OUTBOX_PUBLISH_TOTAL.labels(
            result="success"
        ).inc()

        logger.info(
            "outbox_event_published",
            event_id=event.id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            attempts=event.publish_attempts,
        )

        return True

def update_pending_metric() -> None:
    with SessionLocal() as db:
        pending = db.scalar(
            select(
                func.count()
            )
            .select_from(
                OutboxEvent
            )
            .where(
                OutboxEvent.published_at.is_(
                    None
                )
            )
        )

    OUTBOX_PENDING.set(
        pending or 0
    )


def main() -> None:
    start_http_server(
        9100
    )
    logger.info(
        "outbox_publisher_started",
        queue=(
            settings.payment_events_queue_name
        ),
    )

    client = create_sqs_client()

    queue_url: str | None = None

    while True:
        try:
            
            update_pending_metric()

            if queue_url is None:
                queue_url = get_queue_url(
                    client
                )

            published = publish_next_event(
                client,
                queue_url,
            )

            if not published:
                time.sleep(1)

        except (
            BotoCoreError,
            ClientError,
        ):
            queue_url = None
            time.sleep(2)

        except Exception:
            logger.exception(
                "outbox_publisher_unexpected_error"
            )

            time.sleep(2)


if __name__ == "__main__":
    main()
