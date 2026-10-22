import json
import time

import structlog
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import (
    Base,
    SessionLocal,
    engine,
)
from app.logging import configure_logging
from app.models import Notification
from app.schemas import PaymentSucceededEvent
from app.sqs_client import (
    create_sqs_client,
    get_payment_queue_url,
)
from prometheus_client import (
    Counter,
    start_http_server,
)



configure_logging(
    "notification-service"
)

logger = structlog.get_logger()

EVENTS_RECEIVED_TOTAL = Counter(
    "notification_events_received_total",
    "Payment events received by the notification worker.",
)


NOTIFICATIONS_CREATED_TOTAL = Counter(
    "notifications_created_total",
    "Notifications successfully created.",
)


DUPLICATE_EVENTS_TOTAL = Counter(
    "notification_duplicate_events_total",
    "Duplicate payment events ignored.",
)


EVENT_PROCESSING_FAILURES_TOTAL = Counter(
    "notification_event_processing_failures_total",
    "Notification event processing failures.",
)

def process_message(
    body: str,
) -> bool:
    try:
        raw_event = json.loads(
            body
        )

        event = (
            PaymentSucceededEvent
            .model_validate(raw_event)
        )

    except (
        json.JSONDecodeError,
        ValidationError,
    ):
        EVENT_PROCESSING_FAILURES_TOTAL.inc()

        logger.exception(
            "invalid_payment_event"
        )

        return False

    with SessionLocal() as db:
        existing = db.scalar(
            select(Notification).where(
                Notification.event_id
                == event.event_id
            )
        )

        if existing is not None:
            DUPLICATE_EVENTS_TOTAL.inc()

            logger.info(
                "duplicate_event_ignored",
                event_id=event.event_id,
                notification_id=existing.id,
            )

            return True

        notification = Notification(
            event_id=event.event_id,
            event_type=event.event_type,
            user_id=event.data.user_id,
            order_id=event.data.order_id,
            payment_id=(
                event.data.payment_id
            ),
            amount_cents=(
                event.data.amount_cents
            ),
            channel="simulated_email",
            message=(
                "Payment of "
                f"{event.data.amount_cents} cents "
                "for order "
                f"{event.data.order_id} "
                "succeeded."
            ),
        )

        db.add(notification)

        try:
            db.commit()
            db.refresh(notification)

            NOTIFICATIONS_CREATED_TOTAL.inc()

        except IntegrityError:
            db.rollback()

            existing = db.scalar(
                select(Notification).where(
                    Notification.event_id
                    == event.event_id
                )
            )

            if existing is not None:
                DUPLICATE_EVENTS_TOTAL.inc()

                logger.info(
                    "duplicate_event_ignored",
                    event_id=event.event_id,
                    notification_id=existing.id,
                )

                return True

            raise

        logger.info(
            "notification_created",
            notification_id=notification.id,
            event_id=event.event_id,
            payment_id=event.data.payment_id,
            order_id=event.data.order_id,
            user_id=event.data.user_id,
        )

        return True


def main() -> None:
    start_http_server(
        9100
    )
    Base.metadata.create_all(
        bind=engine
    )

    logger.info(
        "notification_worker_started",
        queue=(
            settings.payment_events_queue_name
        ),
    )

    client = create_sqs_client()

    queue_url: str | None = None

    while True:
        try:
            if queue_url is None:
                queue_url = (
                    get_payment_queue_url(
                        client
                    )
                )

            response = (
                client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=5,
                    WaitTimeSeconds=(
                        settings
                        .sqs_wait_time_seconds
                    ),
                    VisibilityTimeout=(
                        settings
                        .sqs_visibility_timeout_seconds
                    ),
                    MessageSystemAttributeNames=[
                        "ApproximateReceiveCount"
                    ],
                )
            )

            messages = response.get(
                "Messages",
                [],
            )

            for message in messages:
                EVENTS_RECEIVED_TOTAL.inc()

                receive_count = (
                    message
                    .get(
                        "Attributes",
                        {},
                    )
                    .get(
                        "ApproximateReceiveCount",
                        "unknown",
                    )
                )

                logger.info(
                    "payment_event_received",
                    message_id=(
                        message["MessageId"]
                    ),
                    receive_count=receive_count,
                )

                processed = process_message(
                    message["Body"]
                )

                if processed:
                    client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=(
                            message[
                                "ReceiptHandle"
                            ]
                        ),
                    )

                    logger.info(
                        "payment_event_deleted",
                        message_id=(
                            message[
                                "MessageId"
                            ]
                        ),
                    )

        except (
            BotoCoreError,
            ClientError,
        ):
            logger.exception(
                "sqs_worker_error"
            )

            queue_url = None
            time.sleep(2)

        except Exception:
            EVENT_PROCESSING_FAILURES_TOTAL.inc()

            logger.exception(
                "notification_worker_unexpected_error"
            )

            time.sleep(2)


if __name__ == "__main__":
    main()