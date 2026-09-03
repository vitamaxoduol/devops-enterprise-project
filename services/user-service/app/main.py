import structlog
from fastapi import FastAPI, Response, status
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import Base, database_is_ready, engine
from app.logging import configure_logging
from app.routes import router


configure_logging()

logger = structlog.get_logger()


app = FastAPI(
    title="User Service",
    version="1.0.0",
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)

    logger.info(
        "service_started",
        service="user-service",
    )


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {
        "status": "alive",
        "service": "user-service",
    }


@app.get("/health/ready", tags=["health"])
def readiness(response: Response) -> dict[str, str]:
    if not database_is_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "not_ready",
            "database": "unavailable",
        }

    return {
        "status": "ready",
        "database": "available",
    }


app.include_router(router)


Instrumentator().instrument(app).expose(
    app,
    endpoint="/metrics",
)