from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://printuser:printpass@localhost:5432/printcalc")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

APP_DIR = Path(__file__).resolve().parent


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upgrade_database(revision: str = "head") -> None:
    """Bringt das Schema per Alembic auf den aktuellen Stand (ersetzt das frühere create_all)."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(str(APP_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(APP_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False  # uvicorn-Logging nicht überschreiben
    command.upgrade(cfg, revision)
