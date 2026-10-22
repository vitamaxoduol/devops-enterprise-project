import os

from fastapi import FastAPI

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import (
    FastAPIInstrumentor,
)
from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
)
from opentelemetry.instrumentation.sqlalchemy import (
    SQLAlchemyInstrumentor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import (
    TracerProvider,
)
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)


def configure_telemetry(
    *,
    service_name: str,
    app: FastAPI | None = None,
    engine=None,
    instrument_botocore: bool = False,
) -> None:

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv(
                "OTEL_SERVICE_VERSION",
                "0.1.0",
            ),
            "deployment.environment.name": (
                os.getenv(
                    "ENVIRONMENT",
                    "local",
                )
            ),
        }
    )

    provider = TracerProvider(
        resource=resource
    )

    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    if endpoint:
        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=True,
        )

        provider.add_span_processor(
            BatchSpanProcessor(
                exporter
            )
        )

    trace.set_tracer_provider(
        provider
    )

    if app is not None:
        FastAPIInstrumentor.instrument_app(
            app
        )

    HTTPXClientInstrumentor().instrument()

    if engine is not None:
        SQLAlchemyInstrumentor().instrument(
            engine=engine
        )

    if instrument_botocore:
        from opentelemetry.instrumentation.botocore import (
            BotocoreInstrumentor,
        )

        BotocoreInstrumentor().instrument()