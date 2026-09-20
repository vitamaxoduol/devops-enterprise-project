#!/usr/bin/env bash

set -euo pipefail

QUEUE_NAME="${PAYMENT_EVENTS_QUEUE_NAME:-payment-events}"
DLQ_NAME="${PAYMENT_EVENTS_DLQ_NAME:-payment-events-dlq}"

echo "Creating SQS dead-letter queue: ${DLQ_NAME}"

DLQ_URL="$(
    awslocal sqs create-queue \
        --queue-name "$DLQ_NAME" \
        --query 'QueueUrl' \
        --output text
)"

DLQ_ARN="$(
    awslocal sqs get-queue-attributes \
        --queue-url "$DLQ_URL" \
        --attribute-names QueueArn \
        --query 'Attributes.QueueArn' \
        --output text
)"

export DLQ_ARN

python3 - <<'PY'
import json
import os

dlq_arn = os.environ["DLQ_ARN"]

attributes = {
    "VisibilityTimeout": "5",
    "ReceiveMessageWaitTimeSeconds": "10",
    "RedrivePolicy": json.dumps({
        "deadLetterTargetArn": dlq_arn,
        "maxReceiveCount": "3",
    }),
}

with open(
    "/tmp/payment-queue-attributes.json",
    "w",
    encoding="utf-8",
) as file:
    json.dump(attributes, file)
PY

echo "Creating SQS queue: ${QUEUE_NAME}"

QUEUE_URL="$(
    awslocal sqs create-queue \
        --queue-name "$QUEUE_NAME" \
        --attributes file:///tmp/payment-queue-attributes.json \
        --query 'QueueUrl' \
        --output text
)"

echo "Payment events queue: ${QUEUE_URL}"
echo "Payment events DLQ: ${DLQ_URL}"