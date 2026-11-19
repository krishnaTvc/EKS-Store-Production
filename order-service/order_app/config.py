from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "order-service"
    APP_ENV: str = "development"
    PORT: int = 8002
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+psycopg://order_user:order_pass@localhost:5432/orders"
    DATABASE_URL_FILE: str | None = None
    DATABASE_SECRET_DIR: str | None = None
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 1
    CORS_ORIGINS: str = ""  # Comma-separated origins; defaults to empty for same-origin proxying

    # Downstream Catalog Service HTTP client settings
    CATALOG_SERVICE_URL: str = "http://localhost:8001"
    CATALOG_TIMEOUT_SECONDS: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
