import time
from datetime import datetime, timezone

import boto3
import structlog
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.logging import configure_logging
from app.models import OutboxEvent


configure_logging()

logger = structlog.get_logger()


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
            client.send_message(
                QueueUrl=queue_url,
                MessageBody=event.payload,
            )

        except (
            BotoCoreError,
            ClientError,
        ):
            event.publish_attempts += 1
            db.commit()

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

        logger.info(
            "outbox_event_published",
            event_id=event.id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            attempts=event.publish_attempts,
        )

        return True


def main() -> None:
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