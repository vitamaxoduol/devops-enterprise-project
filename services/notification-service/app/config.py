from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://platform:"
        "platform-local-password"
        "@postgres:5432/notification_db"
    )

    aws_endpoint_url: str | None = None
    aws_region: str = "eu-west-1"

    payment_events_queue_name: str = (
        "payment-events"
    )

    sqs_wait_time_seconds: int = 10

    sqs_visibility_timeout_seconds: int = 5

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION_",
        case_sensitive=False,
    )


settings = Settings()