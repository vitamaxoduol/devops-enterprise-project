import logging
import sys

import structlog

from opentelemetry import trace
from app.config import settings


def add_otel_context(
    logger,
    method_name,
    event_dict,
):
    span = trace.get_current_span()

    span_context = (
        span.get_span_context()
    )

    if span_context.is_valid:
        event_dict["trace_id"] = format(
            span_context.trace_id,
            "032x",
        )

        event_dict["span_id"] = format(
            span_context.span_id,
            "016x",
        )

    return event_dict


def configure_logging(
    service_name: str,
) -> None:

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level.upper(),
    )

    def add_service_context(
        logger,
        method_name,
        event_dict,
    ):
        event_dict.setdefault(
            "service",
            service_name,
        )

        event_dict.setdefault(
            "environment",
            settings.environment,
        )

        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,

            add_service_context,

            add_otel_context,

            structlog.processors.add_log_level,

            structlog.processors.TimeStamper(
                fmt="iso"
            ),

            structlog.processors.JSONRenderer(),
        ],

        wrapper_class=(
            structlog.make_filtering_bound_logger(
                getattr(
                    logging,
                    settings.log_level.upper(),
                )
            )
        ),

        cache_logger_on_first_use=True,
    )