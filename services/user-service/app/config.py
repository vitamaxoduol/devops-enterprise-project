from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://platform:platform-local-password"
        "@postgres:5432/user_db"
    )

    model_config = SettingsConfigDict(
        env_prefix="USER_",
        case_sensitive=False,
    )


settings = Settings()