import os
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from order_app.config import settings


def resolve_database_url() -> str:
    # 1. Direct secret file from Secrets Store CSI mount
    if settings.DATABASE_URL_FILE and os.path.isfile(settings.DATABASE_URL_FILE):
        with open(settings.DATABASE_URL_FILE, "r", encoding="utf-8") as f:
            url = f.read().strip()
            if url:
                return url

    # 2. Mounted secret directory containing individual keys
    if settings.DATABASE_SECRET_DIR and os.path.isdir(settings.DATABASE_SECRET_DIR):
        secret_dir = Path(settings.DATABASE_SECRET_DIR)
        url_file = secret_dir / "DATABASE_URL"
        if url_file.is_file():
            url = url_file.read_text(encoding="utf-8").strip()
            if url:
                return url
        user_file = secret_dir / "username"
        pass_file = secret_dir / "password"
        host_file = secret_dir / "host"
        port_file = secret_dir / "port"
        db_file = secret_dir / "dbname"
        if user_file.is_file() and pass_file.is_file() and host_file.is_file():
            u = user_file.read_text(encoding="utf-8").strip()
            p = quote_plus(pass_file.read_text(encoding="utf-8").strip())
            h = host_file.read_text(encoding="utf-8").strip()
            port = port_file.read_text(encoding="utf-8").strip() if port_file.is_file() else "5432"
            db = db_file.read_text(encoding="utf-8").strip() if db_file.is_file() else "orders"
            return f"postgresql+psycopg://{u}:{p}@{h}:{port}/{db}"

    return settings.DATABASE_URL


db_url = resolve_database_url()
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    **({} if db_url.startswith("sqlite") else {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
    })
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
