from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://platform:platform-local-password"
        "@postgres:5432/payment_db"
    )

    order_service_url: str = "http://order-service:8000"

    order_service_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_prefix="PAYMENT_",
        case_sensitive=False,
    )


settings = Settings()