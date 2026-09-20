import boto3

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from app.config import settings


def create_sqs_client():
    return boto3.client(
        "sqs",
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
    )


def get_payment_queue_url(
    client,
) -> str:
    response = client.get_queue_url(
        QueueName=(
            settings.payment_events_queue_name
        )
    )

    return response["QueueUrl"]


def sqs_is_ready() -> bool:
    try:
        client = create_sqs_client()

        get_payment_queue_url(
            client
        )

        return True

    except (
        BotoCoreError,
        ClientError,
    ):
        return False