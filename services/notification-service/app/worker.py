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


configure_logging()

logger = structlog.get_logger()


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
        logger.exception(
            "invalid_payment_event",
            message_body=body,
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

        except IntegrityError:
            db.rollback()

            existing = db.scalar(
                select(Notification).where(
                    Notification.event_id
                    == event.event_id
                )
            )

            if existing is not None:
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
            logger.exception(
                "notification_worker_unexpected_error"
            )

            time.sleep(2)


if __name__ == "__main__":
    main()