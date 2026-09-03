import structlog

from fastapi import FastAPI, Response, status
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import (
    Base,
    database_is_ready,
    engine,
)
from app.logging import configure_logging
from app.routes import router
from app.user_client import user_service_is_ready


configure_logging()

logger = structlog.get_logger()


app = FastAPI(
    title="Order Service",
    version="1.0.0",
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(
        bind=engine
    )

    logger.info(
        "service_started",
        service="order-service",
    )


@app.get(
    "/health/live",
    tags=["health"],
)
def liveness() -> dict[str, str]:
    return {
        "status": "alive",
        "service": "order-service",
    }


@app.get(
    "/health/ready",
    tags=["health"],
)
def readiness(
    response: Response,
) -> dict[str, str]:
    if not database_is_ready():
        response.status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
        )

        return {
            "status": "not_ready",
            "database": "unavailable",
        }

    return {
        "status": "ready",
        "database": "available",
    }


@app.get(
    "/health/dependencies",
    tags=["health"],
)
def dependencies() -> dict:
    user_service_ready = (
        user_service_is_ready()
    )

    return {
        "status": (
            "healthy"
            if user_service_ready
            else "degraded"
        ),
        "dependencies": {
            "user_service": (
                "available"
                if user_service_ready
                else "unavailable"
            )
        },
    }


app.include_router(
    router
)


Instrumentator().instrument(
    app
).expose(
    app,
    endpoint="/metrics",
)