import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "catalog-service"
    APP_ENV: str = "development"
    PORT: int = 8001
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+psycopg://catalog_user:catalog_pass@localhost:5432/catalog"
    DATABASE_URL_FILE: str | None = None
    DATABASE_SECRET_DIR: str | None = None
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 1
    CORS_ORIGINS: str = ""  # Comma-separated origins; defaults to empty for same-origin proxying

    # Image Resolution Configuration
    IMAGE_MODE: str = "local"  # 'local' or 's3'
    LOCAL_ASSETS_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
    LOCAL_IMAGE_BASE_URL: str = "/assets"
    PLACEHOLDER_KEY: str = "catalog/placeholder.png"

    # AWS S3 Settings (used when IMAGE_MODE=s3)
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "eks-beverage-store-catalog"
    S3_PRESIGNED_EXPIRATION_SECONDS: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
