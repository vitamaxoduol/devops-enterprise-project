from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://platform:platform-local-password"
        "@postgres:5432/order_db"
    )

    user_service_url: str = "http://user-service:8000"

    user_service_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_prefix="ORDER_",
        case_sensitive=False,
    )


settings = Settings()